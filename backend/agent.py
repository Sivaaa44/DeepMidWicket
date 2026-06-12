import os
import re
import json
import time
from functools import wraps
from groq import Groq
from dotenv import load_dotenv
from database import run_query, get_schema

# Setup logging
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "agent.log")

def write_log(line: str):
    try:
        print(line)
    except UnicodeEncodeError:
        try:
            print(line.replace("→", "->"))
        except Exception:
            pass
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def timing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        write_log(f"[timing] {func.__name__} → {duration:.2f}s")
        return result
    return wrapper

run_query = timing(run_query)

def sanitise(value) -> str:
    if value is None:
        return ""
    val = str(value).strip()
    for char in ["'", '"', ';', '\\']:
        val = val.replace(char, '')
    return val

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "player_stats",
            "description": "Get stats for a single player — batting, bowling, or allround performance across phases or seasons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name":  {"type": "string", "description": "Player name keyword e.g. 'Kohli', 'Bumrah'"},
                    "stat_type":    {"type": "string", "enum": ["batting", "bowling", "allround"]},
                    "phase":        {"type": "string", "enum": ["overall", "powerplay", "middle", "death"]},
                    "season":       {"type": "string", "description": "e.g. '2024' or null for all seasons"},
                    "specific_stat": {"type": "string", "description": "If user asks for just one stat e.g. 'wickets', 'runs', 'economy', 'strike rate'. Null if full profile asked."}
                },
                "required": ["player_name", "stat_type", "phase"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "player_comparison",
            "description": "Compare two players. Works for batter vs batter, bowler vs bowler, OR batter vs bowler head-to-head.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player1":          {"type": "string"},
                    "player2":          {"type": "string"},
                    "comparison_type":  {"type": "string", "enum": ["batter_vs_batter", "bowler_vs_bowler", "batter_vs_bowler"]},
                    "phase":            {"type": "string", "enum": ["overall", "powerplay", "middle", "death"]}
                },
                "required": ["player1", "player2", "comparison_type", "phase"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "general_query",
            "description": "Teams, venues, seasons, records, win rates, toss stats, season comparisons for a player, purple cap, orange cap, anything not about one or two players in isolation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "general_chat",
            "description": "Greetings, chat, questions about how the app works, app status, or generic queries that do NOT need SQL stats database queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The generic chat question or greeting"}
                },
                "required": ["question"]
            }
        }
    }
]


# ── Tool-Specific System Prompts ──────────────────────────────────────────────

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

Write a single SQLite SELECT query to compare two players.

RULES:
- BOWLER WICKETS: exclude run outs — SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' THEN 1 ELSE 0 END)
- Strike rate = ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Economy = ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
- Phase: powerplay = over 0-5, middle = over 6-14, death = over 15-19
- No minimum thresholds for named player comparisons

For batter_vs_batter:
  - Filter: WHERE batter LIKE '%p1%' OR batter LIKE '%p2%'
  - GROUP BY player label using CASE WHEN
  - Include: runs, balls_faced, strike_rate, average, fours, sixes, dismissals

For bowler_vs_bowler:
  - Filter: WHERE bowler LIKE '%p1%' OR bowler LIKE '%p2%'
  - GROUP BY player label
  - Include: wickets (excluding run outs), balls_bowled, economy, bowling_average, bowling_sr

For batter_vs_bowler (HEAD TO HEAD):
  - Filter: WHERE batter LIKE '%batter%' AND bowler LIKE '%bowler%'
  - Figure out who is batter and who is bowler from context
  - Include: balls_faced, runs_scored, dismissals, strike_rate, dot_balls, fours, sixes
  - dot_balls = COUNT(CASE WHEN runs_batter = 0 AND (extras_type IS NULL OR extras_type NOT IN ('wides','noballs')) THEN 1 END)
  - dismissals = SUM(CASE WHEN is_wicket = 1 AND wicket_kind != 'run out' THEN 1 ELSE 0 END)

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
- Only SELECT, never INSERT/UPDATE/DELETE
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
- QUERY SCOPE: if user asks one specific thing, return only that. Don't add unrequested columns.
- If comparing a player across seasons, GROUP BY m.season and return both seasons in one query

Question: {question}

SQL:"""


GENERAL_CHAT_PROMPT = """You are a helpful cricket intelligence assistant.
Answer the user's question directly and concisely.

User asked: "{question}"

Rules:
- Be helpful, conversational, and direct.
- Do not mention or generate SQL queries.
- If the user asks about the app, explain that this is a Cricket Intelligence App that allows querying IPL statistics, comparing players, and checking match records.
- Keep it under 100 words.
"""


# ── Router ────────────────────────────────────────────────────────────────────

@timing
def route_question(question: str):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cricket analytics router. Pick the right tool.\n\n"
                    "player_stats: one named player, asking about their performance stats\n"
                    "  - Set specific_stat if user asks for just one thing e.g. 'wickets', 'runs', 'economy'\n"
                    "  - Set specific_stat=null if user wants full stats or a profile\n\n"
                    "player_comparison: two players being compared OR head-to-head matchup\n"
                    "  - batter_vs_batter: two batters\n"
                    "  - bowler_vs_bowler: two bowlers\n"
                    "  - batter_vs_bowler: one batter one bowler, head to head\n\n"
                    "general_query: teams, venues, records, season comparisons, purple/orange cap, "
                    "win rates, toss stats, or comparing same player across multiple seasons. ONLY use this for queries requiring database statistics.\n\n"
                    "general_chat: greetings, app status, how the app works, or generic queries that do NOT need database/SQL statistics.\n"
                )
            },
            {"role": "user", "content": question}
        ],
        tools=TOOLS,
        tool_choice="required",
        temperature=0,
    )
    return response.choices[0].message.tool_calls[0], response.usage


# ── SQL Generator ─────────────────────────────────────────────────────────────

@timing
def generate_sql(prompt: str):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_completion_tokens=600,
    )
    sql = response.choices[0].message.content.strip()
    clean_sql = re.sub(r"```sql|```", "", sql).strip()
    return clean_sql, response.usage


# ── Answer Generator ──────────────────────────────────────────────────────────

@timing
def generate_answer(question: str, tool: str, comparison_type: str, columns: list, rows: list):
    if not rows:
        return "No data found. Try rephrasing or check the player/team name.", None

    results_text = " | ".join(columns) + "\n" + "-" * 60 + "\n"
    for row in rows[:20]:
        results_text += " | ".join(str(v) for v in row.values()) + "\n"

    context = {
        "player_stats":      "Give a concise factual breakdown. Highlight what stands out.",
        "player_comparison": (
            "Compare directly. Say who comes out on top and in which areas."
            if comparison_type != "batter_vs_bowler"
            else "Analyze this head-to-head. Who has the upper hand? Mention dismissals and strike rate."
        ),
        "general_query": "Answer directly. Lead with the key stat or finding."
    }.get(tool, "Answer clearly.")

    prompt = f"""You are a cricket analyst giving factual IPL insights.

User asked: "{question}"
{context}

Data:
{results_text}

Rules:
- Always answer the user's question directly before discussing supporting statistics (lead with the answer in the first sentence).
- Do not merely repeat rows from the SQL output.
- Use the provided data to identify trends, strengths and weaknesses, performance patterns, comparisons, outliers, historical changes, or match situation insights.
- Explain the cricketing significance of statistics rather than presenting numbers without context.
- Base conclusions strictly on the provided query results. Never invent statistics, records, matches, seasons, players, events, or explanations not supported by the data.
- If the data is insufficient to support a conclusion, explicitly say so.
- Never say "no wait", "actually", "hmm" or correct yourself mid-sentence.
- Keep the response concise (aim for under 100 words).
- Sound like ESPNCricinfo, not a chatbot."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_completion_tokens=200,
    )
    return response.choices[0].message.content.strip(), response.usage


# ── Main Entry Point ──────────────────────────────────────────────────────────

def ask(question: str) -> dict:
    start_time = time.time()
    tool_name = None
    args = None
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        tool_call, route_usage = route_question(question)
        tool_name = tool_call.function.name
        args      = json.loads(tool_call.function.arguments)

        if route_usage:
            total_input_tokens += getattr(route_usage, "prompt_tokens", 0)
            total_output_tokens += getattr(route_usage, "completion_tokens", 0)

        if tool_name == "general_chat":
            prompt = GENERAL_CHAT_PROMPT.format(question=question)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_completion_tokens=200,
            )
            chat_usage = response.usage
            if chat_usage:
                total_input_tokens += getattr(chat_usage, "prompt_tokens", 0)
                total_output_tokens += getattr(chat_usage, "completion_tokens", 0)

            answer = response.choices[0].message.content.strip()
            duration = time.time() - start_time
            write_log(f'[request] question="{question}" tool={tool_name} rows=0 total={duration:.1f}s')
            return {
                "question": question,
                "tool":     tool_name,
                "args":     args,
                "sql":      None,
                "answer":   answer,
                "data":     {"columns": [], "rows": []},
                "tokens": {
                    "input": total_input_tokens,
                    "output": total_output_tokens,
                    "total": total_input_tokens + total_output_tokens
                }
            }

        schema = get_schema()

        if tool_name == "player_stats":
            player_name_raw = args.get("player_name")
            player_name_san = sanitise(player_name_raw)
            if not player_name_san:
                duration = time.time() - start_time
                write_log(f'[request] question="{question}" tool={tool_name} rows=0 total={duration:.1f}s')
                return {
                    "question": question,
                    "tool":     tool_name,
                    "args":     args,
                    "sql":      None,
                    "answer":   "Couldn't identify the player name. Please try again.",
                    "data":     {"columns": [], "rows": []},
                    "tokens": {
                        "input": total_input_tokens,
                        "output": total_output_tokens,
                        "total": total_input_tokens + total_output_tokens
                    }
                }
            args["player_name"] = player_name_san
            prompt = PLAYER_STATS_PROMPT.format(
                schema=schema,
                player_name=player_name_san,
                stat_type=args.get("stat_type"),
                phase=args.get("phase", "overall"),
                season=args.get("season") or "all seasons",
                specific_stat=args.get("specific_stat") or "null"
            )
        elif tool_name == "player_comparison":
            p1_raw = args.get("player1")
            p2_raw = args.get("player2")
            p1_san = sanitise(p1_raw)
            p2_san = sanitise(p2_raw)
            if not p1_san or not p2_san:
                duration = time.time() - start_time
                write_log(f'[request] question="{question}" tool={tool_name} rows=0 total={duration:.1f}s')
                return {
                    "question": question,
                    "tool":     tool_name,
                    "args":     args,
                    "sql":      None,
                    "answer":   "Both player names must be specified for a comparison. Please try again.",
                    "data":     {"columns": [], "rows": []},
                    "tokens": {
                        "input": total_input_tokens,
                        "output": total_output_tokens,
                        "total": total_input_tokens + total_output_tokens
                    }
                }
            args["player1"] = p1_san
            args["player2"] = p2_san
            prompt = PLAYER_COMPARISON_PROMPT.format(
                schema=schema,
                player1=p1_san,
                player2=p2_san,
                comparison_type=args.get("comparison_type"),
                phase=args.get("phase", "overall")
            )
        else:
            prompt = GENERAL_QUERY_PROMPT.format(
                schema=schema,
                question=question
            )

        sql, sql_usage = generate_sql(prompt)
        if sql_usage:
            total_input_tokens += getattr(sql_usage, "prompt_tokens", 0)
            total_output_tokens += getattr(sql_usage, "completion_tokens", 0)

        columns, rows = run_query(sql)

        comparison_type = args.get("comparison_type", "")
        answer, ans_usage = generate_answer(question, tool_name, comparison_type, columns, rows)
        if ans_usage:
            total_input_tokens += getattr(ans_usage, "prompt_tokens", 0)
            total_output_tokens += getattr(ans_usage, "completion_tokens", 0)

        duration = time.time() - start_time
        write_log(f'[request] question="{question}" tool={tool_name} rows={len(rows)} total={duration:.1f}s')
        return {
            "question": question,
            "tool":     tool_name,
            "args":     args,
            "sql":      sql,
            "answer":   answer,
            "data":     {"columns": columns, "rows": rows},
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens
            }
        }

    except ValueError as e:
        duration = time.time() - start_time
        write_log(f'[request] question="{question}" tool={tool_name} rows=0 total={duration:.1f}s')
        return {
            "question": question,
            "tool":     tool_name,
            "args":     args,
            "sql":      None,
            "answer":   f"Error: {str(e)}",
            "data":     None,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens
            }
        }
    except Exception as e:
        print(f"[error] {str(e)}")
        write_log(f"[error] {str(e)}")
        duration = time.time() - start_time
        write_log(f'[request] question="{question}" tool={tool_name} rows=0 total={duration:.1f}s')
        return {
            "question": question,
            "tool":     tool_name,
            "args":     args,
            "sql":      None,
            "answer":   "An internal error occurred. Please try again later.",
            "data":     None,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "total": total_input_tokens + total_output_tokens
            }
        }