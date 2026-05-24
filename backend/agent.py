import os
import re
import json
from groq import Groq
from dotenv import load_dotenv
from database import run_query, get_schema

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ── Tool Definitions (for router) ─────────────────────────────────────────────

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
                    "season":       {"type": "string", "description": "e.g. '2024' or null for all seasons"}
                },
                "required": ["player_name", "stat_type", "phase"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "player_comparison",
            "description": "Compare two players. Works for batter vs batter, bowler vs bowler, OR batter vs bowler head-to-head (how many times one got the other out, runs scored off them, etc).",
            "parameters": {
                "type": "object",
                "properties": {
                    "player1":      {"type": "string", "description": "First player name keyword"},
                    "player2":      {"type": "string", "description": "Second player name keyword"},
                    "comparison_type": {
                        "type": "string",
                        "enum": ["batter_vs_batter", "bowler_vs_bowler", "batter_vs_bowler"],
                        "description": "batter_vs_bowler = head to head matchup, who got who out, runs scored off them"
                    },
                    "phase":        {"type": "string", "enum": ["overall", "powerplay", "middle", "death"]}
                },
                "required": ["player1", "player2", "comparison_type", "phase"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "general_query",
            "description": "Answer general questions about teams, venues, seasons, records, win rates, toss stats — anything not about one or two specific players.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"}
                },
                "required": ["question"]
            }
        }
    }
]


# ── Tool-Specific System Prompts ──────────────────────────────────────────────

PLAYER_STATS_PROMPT = """You are an expert cricket analyst and SQLite query writer specializing in IPL player performance.

{schema}

Your job: write a single SQLite SELECT query for individual player stats.

PLAYER STATS RULES:
- Always use LIKE '%player_name%' for name matching
- For batting stats include: matches, runs, balls_faced, strike_rate, average, fours, sixes, highest_score, dismissals
- For bowling stats include: matches, wickets, balls_bowled, runs_conceded, economy, bowling_average, bowling_sr, best figures
- For allround: include both batting and bowling in one query using UNION or separate columns
- Strike rate = SUM(runs_batter) * 100.0 / COUNT(balls where extras_type != 'wides')
- Economy = SUM(runs_total) * 6.0 / COUNT(balls where extras_type != 'wides')
- Bowling average = runs_conceded / wickets
- Bowling SR = balls_bowled / wickets
- Best figures: find the match where the bowler took most wickets, then least runs in that match
- Phase filters: powerplay = over 0-5, middle = over 6-14, death = over 15-19
- Season filter: m.season = 'YYYY' (TEXT, use quotes)
- Always JOIN matches when filtering by season

Return ONLY the raw SQL, no markdown, no explanation.

Player: {player_name}
Stat type: {stat_type}
Phase: {phase}
Season: {season}

SQL:"""


PLAYER_COMPARISON_PROMPT = """You are an expert cricket analyst and SQLite query writer specializing in IPL head-to-head analysis.

{schema}

Your job: write a single SQLite SELECT query to compare two players.

COMPARISON TYPE RULES:

For batter_vs_batter:
- Compare both players' batting stats side by side
- Include: runs, balls_faced, strike_rate, average, fours, sixes, dismissals
- Use CASE WHEN batter LIKE '%p1%' THEN 'Player1' ELSE 'Player2' END to label rows
- Filter: WHERE batter LIKE '%p1%' OR batter LIKE '%p2%'
- GROUP BY the player label

For bowler_vs_bowler:
- Compare both players' bowling stats side by side
- Include: wickets, balls_bowled, economy, bowling_average, bowling_sr
- Use CASE WHEN bowler LIKE '%p1%' THEN 'Player1' ELSE 'Player2' END
- Filter: WHERE bowler LIKE '%p1%' OR bowler LIKE '%p2%'

For batter_vs_bowler (HEAD TO HEAD MATCHUP):
- This is the most interesting: how did batter perform against this specific bowler
- Query: filter WHERE batter LIKE '%batter%' AND bowler LIKE '%bowler%'
- Include: balls_faced, runs_scored, dismissals (times batter got out to this bowler),
  strike_rate, dot_balls, fours, sixes, wicket_kinds (caught/bowled/lbw breakdown)
- Also show: what % of their matchups ended in a wicket
- Figure out who is the batter and who is the bowler from context

GENERAL RULES:
- Strike rate = runs * 100.0 / valid_balls
- Economy = runs_total * 6.0 / valid_balls  
- valid_balls = COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END)
- Phase: powerplay = over 0-5, middle = over 6-14, death = over 15-19
- Never use SUM(over) for overs bowled

Return ONLY the raw SQL, no markdown, no explanation.

Player 1: {player1}
Player 2: {player2}
Comparison type: {comparison_type}
Phase: {phase}

SQL:"""


GENERAL_QUERY_PROMPT = """You are an expert cricket analyst and SQLite query writer for IPL data.

{schema}

Your job: write a single SQLite SELECT query to answer the question.

RULES:
- Return ONLY raw SQL, no markdown, no backticks, no explanation
- Only SELECT queries, never INSERT/UPDATE/DELETE
- Use LIKE '%name%' for player/team name searches
- Never use SUM(over) to calculate overs bowled
- Economy = SUM(runs_total) * 6.0 / COUNT(valid_balls)
- Strike rate = SUM(runs_batter) * 100.0 / COUNT(valid_balls)
- valid_balls = COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END)
- Finals filter: WHERE m.match_number = (SELECT MAX(match_number) FROM matches m2 WHERE m2.season = m.season)
- For ranking bowlers/batters always apply minimum threshold (200 balls for batters, 300 for bowlers)
- Seasons stored as TEXT: '2008', '2023', '2007/08', '2020/21'
- Always JOIN matches ON match_id when filtering by season, venue, or team
- Limit to 15 rows unless a single value is asked for

Question: {question}

SQL:"""


# ── Router ────────────────────────────────────────────────────────────────────

def route_question(question: str) -> dict:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a cricket analytics router. Pick the right tool based on the question.\n"
                    "- player_stats: one player mentioned, asking about their performance\n"
                    "- player_comparison: two players mentioned OR head-to-head matchup (batter vs bowler)\n"
                    "- general_query: teams, venues, seasons, records, win rates, anything else\n"
                    "For player_comparison, set comparison_type carefully:\n"
                    "  batter_vs_batter = two batters compared\n"
                    "  bowler_vs_bowler = two bowlers compared\n"
                    "  batter_vs_bowler = one batter one bowler, head to head matchup"
                )
            },
            {"role": "user", "content": question}
        ],
        tools=TOOLS,
        tool_choice="required",
        temperature=0,
    )
    print("response of router: ", response)
    print("tool called: ", response.choices[0].message.tool_calls[0])

    return response.choices[0].message.tool_calls[0]


# ── SQL Generator ─────────────────────────────────────────────────────────────

def generate_sql(prompt: str) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_completion_tokens=600,
    )
    sql = response.choices[0].message.content.strip()
    return re.sub(r"```sql|```", "", sql).strip()


# ── Answer Generator ──────────────────────────────────────────────────────────

def generate_answer(question: str, tool: str, comparison_type: str, columns: list, rows: list) -> str:
    if not rows:
        return "I couldn't find any data matching your question. Try rephrasing or check the player/team name."

    results_text = " | ".join(columns) + "\n" + "-" * 60 + "\n"
    for row in rows[:20]:
        results_text += " | ".join(str(v) for v in row.values()) + "\n"

    context = {
        "player_stats":     "Give a detailed breakdown of this player's numbers. Highlight what stands out.",
        "player_comparison": (
            "Compare these two players head to head. Be direct about who comes out on top and in which areas."
            if comparison_type != "batter_vs_bowler"
            else "Analyze this batter vs bowler head-to-head. Who has the upper hand? How many times has the bowler dismissed the batter? What's the batter's strike rate against them?"
        ),
        "general_query":    "Answer directly. Lead with the key stat or finding."
    }.get(tool, "Answer clearly and concisely.")

    prompt = f"""You are a sharp cricket analyst commenting on IPL data.
User asked: "{question}"
{context}

Data:
{results_text}

Keep it under 100 words. Be direct. Sound like a cricket analyst."""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_completion_tokens=300,
    )
    return response.choices[0].message.content.strip()


# ── Main Entry Point ──────────────────────────────────────────────────────────

def ask(question: str) -> dict:
    try:
        # Step 1: route
        tool_call = route_question(question)
        tool_name = tool_call.function.name
        args      = json.loads(tool_call.function.arguments)

        # Step 2: build prompt for the right tool
        schema = get_schema()

        if tool_name == "player_stats":
            prompt = PLAYER_STATS_PROMPT.format(
                schema=schema,
                player_name=args.get("player_name"),
                stat_type=args.get("stat_type"),
                phase=args.get("phase", "overall"),
                season=args.get("season") or "all seasons"
            )
        elif tool_name == "player_comparison":
            prompt = PLAYER_COMPARISON_PROMPT.format(
                schema=schema,
                player1=args.get("player1"),
                player2=args.get("player2"),
                comparison_type=args.get("comparison_type"),
                phase=args.get("phase", "overall")
            )
        else:
            prompt = GENERAL_QUERY_PROMPT.format(
                schema=schema,
                question=question
            )

        # Step 3: generate and run SQL
        sql = generate_sql(prompt)
        columns, rows = run_query(sql)

        # Step 4: generate answer
        comparison_type = args.get("comparison_type", "")
        answer = generate_answer(question, tool_name, comparison_type, columns, rows)

        return {
            "question": question,
            "tool":     tool_name,
            "args":     args,
            "sql":      sql,
            "answer":   answer,
            "data":     {"columns": columns, "rows": rows}
        }

    except Exception as e:
        return {
            "question": question,
            "tool":     None,
            "args":     None,
            "sql":      None,
            "answer":   f"Sorry, I ran into an error: {str(e)}",
            "data":     None
        }