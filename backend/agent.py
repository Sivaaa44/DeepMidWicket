"""
Cricket Intelligence agent: route a question to a tool, generate SQL, run it, and
write an analyst-style answer. Conversation context comes from memory.py.
"""
import json
import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler

import groq

import config
import memory
from database import QueryError, get_dataset_summary, get_schema, run_query

# ── Logging ──────────────────────────────────────────────────────────────────

os.makedirs(config.LOG_DIR, exist_ok=True)
log = logging.getLogger("agent")
if not log.handlers:
    _file = RotatingFileHandler(os.path.join(config.LOG_DIR, "agent.log"),
                                maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    _file.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_file)
    log.setLevel(logging.INFO)


# ── Errors & usage accounting ────────────────────────────────────────────────

class AgentError(Exception):
    """A failure with a stable code and a message that is safe to show users."""

    def __init__(self, code: str, message: str, detail: str = None):
        super().__init__(detail or message)
        self.code = code
        self.message = message
        self.detail = detail or message


class Usage:
    """Token accumulator that survives exceptions, so failed requests are still billed accurately."""

    def __init__(self):
        self.input = 0
        self.output = 0

    def add(self, usage):
        if usage:
            self.input += getattr(usage, "prompt_tokens", 0) or 0
            self.output += getattr(usage, "completion_tokens", 0) or 0

    def as_dict(self):
        return {"input": self.input, "output": self.output, "total": self.input + self.output}


_client = None


def llm_client() -> groq.Groq:
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise AgentError("llm_unconfigured", "The AI service is not configured. Please contact the administrator.",
                             "GROQ_API_KEY is not set")
        _client = groq.Groq(api_key=config.GROQ_API_KEY, timeout=config.LLM_TIMEOUT_SECONDS,
                            max_retries=config.LLM_MAX_RETRIES)
    return _client


def is_reasoning_model(model: str) -> bool:
    return "gpt-oss" in (model or "").lower()


def llm_call(usage: Usage, stage: str, **kwargs):
    """One chat completion with consistent error mapping and usage tracking."""
    kwargs.setdefault("model", config.LLM_MODEL)
    if is_reasoning_model(kwargs["model"]):
        kwargs.setdefault("reasoning_effort", config.LLM_REASONING_EFFORT)
        kwargs.setdefault("include_reasoning", False)
    started = time.perf_counter()
    try:
        response = llm_client().chat.completions.create(**kwargs)
    except groq.RateLimitError as e:
        raise AgentError("llm_rate_limited", "The AI service is busy right now. Please try again in a moment.", str(e)) from e
    except (groq.APITimeoutError, groq.APIConnectionError) as e:
        raise AgentError("llm_unavailable", "Couldn't reach the AI service. Please try again.", str(e)) from e
    except (groq.AuthenticationError, groq.PermissionDeniedError) as e:
        raise AgentError("llm_unconfigured", "The AI service is misconfigured. Please contact the administrator.", str(e)) from e
    except groq.APIError as e:
        raise AgentError("llm_error", "The AI service returned an error. Please try again.", str(e)) from e
    usage.add(response.usage)
    log.info("[llm] stage=%s model=%s %.2fs", stage, kwargs["model"], time.perf_counter() - started)
    choice = response.choices[0]
    if getattr(choice, "finish_reason", None) == "length" and not kwargs.get("tools"):
        # Output hit max_completion_tokens: the text is cut off mid-way and must not be used.
        raise AgentError(
            "llm_truncated",
            "The AI model ran out of room before finishing. Try a narrower question.",
            f"stage={stage} model={kwargs['model']} max_completion_tokens={kwargs.get('max_completion_tokens')} "
            f"partial={(choice.message.content or '')[:200]!r}",
        )
    return response


# ── Tools ────────────────────────────────────────────────────────────────────

PHASES = ["overall", "powerplay", "middle", "death"]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "player_stats",
            "description": "Stats for ONE named player: batting, bowling or all-round, optionally by phase or season.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {"type": "string", "description": "The player's name, with pronouns resolved from context, e.g. 'Kohli', 'Bumrah'"},
                    "stat_type": {"type": "string", "enum": ["batting", "bowling", "allround"]},
                    "phase": {"type": "string", "enum": PHASES},
                    "season": {"type": "string", "description": "Season year e.g. '2024'. Omit when not filtering by season."},
                    "specific_stat": {"type": "string", "description": "Set when the user wants a single statistic (e.g. 'wickets', 'economy'). Omit for a full profile."},
                },
                "required": ["player_name", "stat_type", "phase"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "player_comparison",
            "description": "Compare exactly TWO players: batter vs batter, bowler vs bowler, or a batter vs bowler head-to-head.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player1": {"type": "string", "description": "First player (the batter for head-to-head)"},
                    "player2": {"type": "string", "description": "Second player (the bowler for head-to-head)"},
                    "comparison_type": {"type": "string", "enum": ["batter_vs_batter", "bowler_vs_bowler", "batter_vs_bowler"]},
                    "phase": {"type": "string", "enum": PHASES},
                },
                "required": ["player1", "player2", "comparison_type", "phase"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "general_query",
            "description": "Teams, venues, seasons, records, rankings, win rates, toss stats, caps, a player across seasons, or three or more players.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The user's question rewritten to be fully self-contained: replace pronouns and "
                                       "references ('he', 'that team', 'same season') with the actual names/years from the conversation.",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "general_chat",
            "description": "Greetings, small talk, questions about this app, or cricket questions that need no database statistics.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string"}},
                "required": ["question"],
            },
        },
    },
]

ROUTER_PROMPT = """You are the router for an IPL cricket analytics assistant. Pick exactly one tool.

player_stats: one named player's performance.
  - Set specific_stat when only one number is asked for ("how many wickets", "his economy"); omit it for a profile.
player_comparison: EXACTLY two players.
  - batter_vs_batter / bowler_vs_bowler, or batter_vs_bowler for a head-to-head matchup.
general_query: teams, venues, records, rankings, three or more players, season-by-season trends, caps, toss/win stats.
general_chat: greetings, app questions, or cricket chat that needs no database statistics.

Resolve follow-ups using the conversation context: "his", "him", "they", "that season", "what about in the death overs"
all refer to the most recent matching entity. Always pass real names and years in the arguments, never pronouns."""


# ── SQL prompts ──────────────────────────────────────────────────────────────

PLAYER_STATS_PROMPT = """You are an expert cricket analyst and SQLite query writer for IPL data.

{schema}

Write a single SQLite SELECT query for this player stat request.

RULES:
- Use LIKE '%player_name%' for name matching
- NEVER apply a minimum ball/over threshold for a named player query — thresholds are only for rankings
- BOWLER WICKETS: always exclude run outs — use SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' THEN 1 ELSE 0 END)
- Never use SUM(is_wicket) directly for bowler wicket counts
- Strike rate = ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Economy = ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Bowling average = ROUND(runs_conceded * 1.0 / NULLIF(wickets, 0), 2)
- Bowling SR = ROUND(balls_bowled * 1.0 / NULLIF(wickets, 0), 2)
- Season filter: JOIN matches m ON d.match_id = m.match_id AND m.season = 'YYYY'
- Phase: powerplay = over 0-5, middle = over 6-14, death = over 15-19
- Return a single row. Name columns in snake_case (e.g. runs, balls_faced, strike_rate).

BEST FIGURES (keep it simple):
  best_figures_wickets: (SELECT MAX(wk) FROM (SELECT SUM(CASE WHEN is_wicket=1 AND wicket_kind!='run out' THEN 1 ELSE 0 END) AS wk FROM deliveries WHERE bowler LIKE '%name%' GROUP BY match_id) t)
  Do NOT calculate best_figures_runs — too complex, omit it.

QUERY SCOPE — match what the user actually asked for:
- If user asked for just ONE stat (e.g. "how many wickets", "what is his economy"), return ONLY that stat. Do not add unrequested columns.
- If user asked for a full profile or general stats, return the full relevant stat set for batting or bowling.

Return ONLY raw SQL, no markdown, no explanation.

Player: {player_name}
Stat type: {stat_type}
Phase: {phase}
Season: {season}
Specific stat requested: {specific_stat}

SQL:"""

PLAYER_COMPARISON_PROMPT = """You are an expert cricket analyst and SQLite query writer for IPL data.

{schema}

Write a single SQLite SELECT query to compare players.

RULES:
- BOWLER WICKETS: exclude run outs — SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' THEN 1 ELSE 0 END)
- Strike rate = ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Economy = ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Phase: powerplay = over 0-5, middle = over 6-14, death = over 15-19
- No minimum thresholds for named player comparisons

For batter_vs_batter:
  - Filter: WHERE batter LIKE '%p1%' OR batter LIKE '%p2%'
  - GROUP BY player label using CASE WHEN, labelling each row with the real player name
  - Include columns: player, runs, balls, strike_rate, average, fours, sixes, dismissals

For bowler_vs_bowler:
  - Filter: WHERE bowler LIKE '%p1%' OR bowler LIKE '%p2%'
  - GROUP BY player label using CASE WHEN AS player
  - Include columns: player, wickets, balls_bowled, economy, bowling_average, bowling_sr

For batter_vs_bowler (HEAD TO HEAD):
  - Filter: WHERE batter LIKE '%batter%' AND bowler LIKE '%bowler%'
  - Include: balls_faced, runs_scored, dismissals, strike_rate, dot_balls, fours, sixes
  - dot_balls = COUNT(CASE WHEN runs_batter = 0 AND (extras_type IS NULL OR extras_type NOT IN ('wides','noballs')) THEN 1 END)
  - dismissals = SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' AND player_out = batter THEN 1 ELSE 0 END)

Return ONLY raw SQL, no markdown, no explanation.

Player 1: {player1}
Player 2: {player2}
Comparison type: {comparison_type}
Phase: {phase}

SQL:"""

GENERAL_QUERY_PROMPT = """You are an expert cricket analyst and SQLite query writer for IPL data.

{schema}

Write a single SQLite SELECT query to answer the question.

RULES:
- Return ONLY raw SQL, no markdown, no backticks, no explanation
- Only SELECT (or WITH ... SELECT), never INSERT/UPDATE/DELETE
- Use LIKE '%name%' for player/team name searches
- BOWLER WICKETS: always use SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' THEN 1 ELSE 0 END) — never SUM(is_wicket)
- Economy = ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Strike rate = ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Never use SUM(over) to calculate overs bowled
- Finals: WHERE m.match_number = (SELECT MAX(match_number) FROM matches m2 WHERE m2.season = m.season)
- Minimum thresholds for rankings: 200 balls for batters, 300 balls for bowlers
- Seasons are TEXT: '2008', '2023', '2007/08', '2020/21'
- Always JOIN matches when filtering by season, venue, or city
- Limit to 15 rows unless a single value is requested
- Put the label column (player, team, season, venue) first, then numeric columns, in snake_case
- QUERY SCOPE: if user asks one specific thing, return only that. Don't add unrequested columns.
- If comparing multiple players (3 or more): GROUP BY player name, 1 row per player
- If comparing a player across seasons, GROUP BY m.season and ORDER BY m.season

Question: {question}

SQL:"""

SQL_REPAIR_SUFFIX = """

Your previous query failed.
Previous query:
{sql}
Error: {error}

Write a corrected SQLite SELECT query. Return ONLY raw SQL."""

CHAT_PROMPT = """You are DeepMidWicket, a cricket intelligence assistant for IPL statistics.
{context}
The database covers {dataset}. Users can ask about player stats, head-to-heads, comparisons,
team records, venues, seasons and phases (powerplay, middle, death overs).

User asked: "{question}"

Rules:
- Be helpful, conversational and direct. Keep it under 100 words.
- Do not mention or write SQL.
- Never invent statistics; suggest a question the user could ask instead."""

ANSWER_PROMPT = """You are a cricket analyst giving factual IPL insights.

{context}User asked: "{question}"
{guidance}

Data ({row_count} rows{truncated}):
{results}

Rules:
- Lead with the direct answer in the first sentence.
- Don't merely repeat rows; explain what stands out — trends, strengths, outliers, comparisons.
- Base conclusions strictly on the data. Never invent numbers, matches, seasons or players.
- If the data is insufficient, say so plainly.
- You may wrap the single most important figure or name in **bold**. No headings, no tables.
- Under 100 words. Sound like ESPNCricinfo, not a chatbot."""

SUMMARY_PROMPT = """You maintain a running summary of a conversation about IPL cricket statistics.
Fold the new messages into the existing summary.

Existing summary:
{summary}

New messages:
{messages}

Write an updated prose summary under 100 words. Keep the players, teams, seasons and key numbers discussed,
and what the user seems interested in. No bullet points, no JSON."""

ANSWER_GUIDANCE = {
    "player_stats": "Give a concise factual breakdown. Highlight what stands out.",
    "player_comparison": "Compare directly. Say who comes out on top and in which areas.",
    "head_to_head": "Analyse this head-to-head. Who has the upper hand? Mention dismissals and strike rate.",
    "general_query": "Answer directly. Lead with the key stat or finding.",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

_dataset_desc = None


def dataset_description() -> str:
    global _dataset_desc
    if _dataset_desc is None:
        try:
            s = get_dataset_summary()
            _dataset_desc = (f"{s['matches']:,} IPL matches and {s['deliveries']:,} deliveries, "
                             f"seasons {s['first_season']} to {s['last_season']}")
        except Exception:  # noqa: BLE001
            _dataset_desc = "IPL ball-by-ball data"
    return _dataset_desc


def sanitise(value) -> str:
    """Strip characters that could break out of a LIKE '%...%' literal."""
    if value is None:
        return ""
    val = str(value).strip()
    for char in ["'", '"', ";", "\\", "%", "_"]:
        val = val.replace(char, "" if char not in "%_" else " ")
    return " ".join(val.split())


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _emit(on_event, stage: str, **payload):
    if on_event:
        try:
            on_event({"type": "status", "stage": stage, **payload})
        except Exception:  # noqa: BLE001 - a broken listener must never break the request
            pass


def _parse_args(raw: str) -> dict:
    try:
        args = json.loads(raw or "{}")
        return args if isinstance(args, dict) else {}
    except ValueError:
        return {}


# ── Pipeline stages ──────────────────────────────────────────────────────────

def route_question(question: str, context_str: str, usage: Usage):
    system = ROUTER_PROMPT
    if context_str:
        system = f"{context_str}\n\n{ROUTER_PROMPT}"
    try:
        response = llm_call(
            usage, "route",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": question}],
            tools=TOOLS, tool_choice="required", temperature=0,
        )
    except AgentError as e:
        # Llama occasionally emits a malformed tool call; fall back to a free-form query.
        if e.code == "llm_error" and "tool" in e.detail.lower():
            log.warning("[route] tool call failed, falling back to general_query: %s", e.detail)
            return "general_query", {"question": question}
        raise
    calls = response.choices[0].message.tool_calls or []
    if not calls:
        return "general_query", {"question": question}
    name = calls[0].function.name
    if name not in {t["function"]["name"] for t in TOOLS}:
        return "general_query", {"question": question}
    return name, _parse_args(calls[0].function.arguments)


def build_sql_prompt(tool: str, args: dict, question: str) -> str:
    schema = get_schema()
    if tool == "player_stats":
        name = sanitise(args.get("player_name"))
        if not name:
            raise AgentError("missing_player", "I couldn't tell which player you mean. Could you name them?")
        args["player_name"] = name
        args["phase"] = args.get("phase") if args.get("phase") in PHASES else "overall"
        return PLAYER_STATS_PROMPT.format(
            schema=schema, player_name=name, stat_type=args.get("stat_type") or "batting",
            phase=args["phase"], season=args.get("season") or "all seasons",
            specific_stat=args.get("specific_stat") or "null",
        )
    if tool == "player_comparison":
        p1, p2 = sanitise(args.get("player1")), sanitise(args.get("player2"))
        if not p1 or not p2:
            raise AgentError("missing_player", "A comparison needs two players. Which two should I compare?")
        args["player1"], args["player2"] = p1, p2
        args["phase"] = args.get("phase") if args.get("phase") in PHASES else "overall"
        return PLAYER_COMPARISON_PROMPT.format(
            schema=schema, player1=p1, player2=p2,
            comparison_type=args.get("comparison_type") or "batter_vs_batter", phase=args["phase"],
        )
    standalone = (args.get("question") or "").strip() or question
    args["question"] = standalone
    return GENERAL_QUERY_PROMPT.format(schema=schema, question=standalone)


def generate_sql(prompt: str, usage: Usage) -> str:
    response = llm_call(usage, "sql", messages=[{"role": "user", "content": prompt}],
                        temperature=0.1, max_completion_tokens=config.MAX_TOKENS_SQL)
    return response.choices[0].message.content or ""


def query_with_repair(prompt: str, usage: Usage, on_event=None):
    """Generate SQL and execute it; on failure, feed the error back for a corrected query."""
    _emit(on_event, "sql")
    sql = generate_sql(prompt, usage)
    attempts = 0
    while True:
        _emit(on_event, "query")
        try:
            return run_query(sql)
        except QueryError as e:
            if attempts >= config.SQL_REPAIR_ATTEMPTS:
                raise AgentError(
                    "query_failed",
                    "I couldn't build a working query for that. Try rephrasing, or name the player, team or season explicitly.",
                    f"{e} | sql={sql}",
                ) from e
            attempts += 1
            log.warning("[sql] repair attempt %d after error: %s", attempts, e)
            _emit(on_event, "sql", repair=True)
            sql = generate_sql(prompt + SQL_REPAIR_SUFFIX.format(sql=sql, error=e), usage)


def generate_answer(question: str, guidance_key: str, columns, rows, context_str: str, usage: Usage) -> str:
    table = " | ".join(columns) + "\n" + "\n".join(
        " | ".join("" if v is None else str(v) for v in row.values()) for row in rows[:25]
    )
    prompt = ANSWER_PROMPT.format(
        context=f"{context_str}\n\n" if context_str else "",
        question=question,
        guidance=ANSWER_GUIDANCE.get(guidance_key, "Answer clearly."),
        row_count=len(rows),
        truncated=", showing first 25" if len(rows) > 25 else "",
        results=table,
    )
    response = llm_call(usage, "answer", messages=[{"role": "user", "content": prompt}],
                        temperature=0.3, max_completion_tokens=config.MAX_TOKENS_ANSWER)
    return (response.choices[0].message.content or "").strip()


def summarize(old_summary: str, messages: list[dict], usage: Usage) -> str:
    transcript = "\n".join(f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in messages)
    response = llm_call(
        usage, "summary", model=config.LLM_FAST_MODEL,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(summary=old_summary or "(none)", messages=transcript)}],
        temperature=0.2, max_completion_tokens=config.MAX_TOKENS_SUMMARY,
    )
    return (response.choices[0].message.content or "").strip()


# ── Entry point ──────────────────────────────────────────────────────────────

def ask(question: str, session_id: str = None, on_event=None, context: dict = None) -> dict:
    """
    Answer one question. Never raises: failures come back as result["error"] =
    {"code", "message"} with whatever tokens were consumed before the failure.
    """
    started = time.perf_counter()
    usage = Usage()
    timings = {}
    result = {
        "question": question, "tool": None, "args": {}, "sql": None, "answer": "",
        "data": {"columns": [], "rows": [], "row_count": 0}, "error": None,
    }
    try:
        ctx = context if context is not None else memory.load_context(session_id)
        context_str = memory.format_context(ctx)

        _emit(on_event, "route")
        t = time.perf_counter()
        tool, args = route_question(question, context_str, usage)
        timings["route_ms"] = _ms(t)
        result["tool"], result["args"] = tool, args
        _emit(on_event, "routed", tool=tool, args=args)

        if tool == "general_chat":
            _emit(on_event, "answer")
            t = time.perf_counter()
            prompt = CHAT_PROMPT.format(
                context=f"\n{context_str}\n" if context_str else "",
                dataset=dataset_description(), question=question,
            )
            response = llm_call(usage, "chat", messages=[{"role": "user", "content": prompt}],
                                temperature=0.4, max_completion_tokens=config.MAX_TOKENS_ANSWER)
            result["answer"] = (response.choices[0].message.content or "").strip()
            timings["answer_ms"] = _ms(t)
        else:
            prompt = build_sql_prompt(tool, args, question)
            t = time.perf_counter()
            sql, columns, rows = query_with_repair(prompt, usage, on_event)
            timings["query_ms"] = _ms(t)
            result["sql"] = sql
            result["data"] = {"columns": columns, "rows": rows, "row_count": len(rows)}

            if not rows:
                result["answer"] = ("No matching data found. Check the spelling of the player or team, "
                                    "or try a different season or phase.")
            else:
                _emit(on_event, "answer")
                t = time.perf_counter()
                guidance = tool
                if tool == "player_comparison" and args.get("comparison_type") == "batter_vs_bowler":
                    guidance = "head_to_head"
                result["answer"] = generate_answer(question, guidance, columns, rows, context_str, usage)
                timings["answer_ms"] = _ms(t)

    except AgentError as e:
        log.warning("[ask] error code=%s detail=%s", e.code, e.detail)
        result["error"] = {"code": e.code, "message": e.message, "detail": e.detail}
        result["answer"] = e.message
    except Exception as e:  # noqa: BLE001
        log.exception("[ask] unexpected failure")
        result["error"] = {"code": "internal_error", "message": "Something went wrong on our side. Please try again.",
                           "detail": f"{type(e).__name__}: {e}"}
        result["answer"] = result["error"]["message"]

    timings["total_ms"] = _ms(started)
    result["tokens"] = usage.as_dict()
    result["timings"] = timings
    log.info('[ask] q="%s" tool=%s rows=%s error=%s total=%dms tokens=%d',
             question[:120], result["tool"], result["data"]["row_count"],
             (result["error"] or {}).get("code"), timings["total_ms"], usage.as_dict()["total"])
    return result
