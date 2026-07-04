import os
import re
import json
import time
import threading
from functools import wraps
# pyrefly: ignore [missing-import]
from groq import Groq
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
import redis
from database import run_query, get_schema
from auth_database import save_message, get_recent_messages, save_session_state, get_session_state

# Setup Redis Client
REDIS_URL = os.getenv("REDIS_URL")

redis_client = None
use_redis = False

try:
    if REDIS_URL:
        redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=1.0  # Fail fast if Redis is offline
        )
    else:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
            socket_timeout=1.0  # Fail fast if Redis is offline
        )
    redis_client.ping()
    use_redis = True
    print("[redis] Connected successfully to Redis.")
except Exception as e:
    print(f"[redis] Connection failed: {e}. Falling back to SQLite.")
    use_redis = False


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

# ── Context Management & Session Helpers ─────────────────────────────────────

KNOWN_PEOPLE = set()
KNOWN_ORGANIZATIONS = set()
KNOWN_PLACES = set()

def load_known_entities():
    global KNOWN_PEOPLE, KNOWN_ORGANIZATIONS, KNOWN_PLACES
    try:
        import sqlite3
        db_file = os.path.join(os.path.dirname(__file__), "cricket.db")
        if os.path.exists(db_file):
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Fetch teams (organizations)
            cursor.execute("SELECT DISTINCT team1 FROM matches UNION SELECT DISTINCT team2 FROM matches")
            teams = {row[0].strip() for row in cursor.fetchall() if row[0]}
            
            # Fetch batters and bowlers (people)
            cursor.execute("SELECT DISTINCT batter FROM deliveries UNION SELECT DISTINCT bowler FROM deliveries")
            players = {row[0].strip() for row in cursor.fetchall() if row[0]}
            
            # Fetch player of the match (people)
            cursor.execute("SELECT DISTINCT player_of_match FROM matches")
            pom = {row[0].strip() for row in cursor.fetchall() if row[0]}
            
            # Fetch venues and cities (places)
            cursor.execute("SELECT DISTINCT venue FROM matches UNION SELECT DISTINCT city FROM matches")
            places = {row[0].strip() for row in cursor.fetchall() if row[0]}
            
            conn.close()
            
            KNOWN_PEOPLE = players.union(pom)
            KNOWN_ORGANIZATIONS = teams
            KNOWN_PLACES = places
            
            print(f"[entities] Loaded {len(KNOWN_PEOPLE)} people, {len(KNOWN_ORGANIZATIONS)} organizations, and {len(KNOWN_PLACES)} places.")
    except Exception as e:
        print(f"[entities] Failed to load known entities: {e}")

load_known_entities()

def extract_entities_rule_based(text: str) -> dict:
    text_lower = text.lower()
    
    # Helper to parse words and track their original capitalization (useful to identify proper nouns)
    def parse_query_words(txt: str):
        words_list = []
        caps_list = []
        # Find all words (alphanumeric sequences)
        for match in re.finditer(r'\b\w+\b', txt):
            word = match.group()
            # Ignore single letter 's' which is usually possessive suffix from "Kohli's"
            if word.lower() == 's':
                continue
            words_list.append(word.lower())
            caps_list.append(word[0].isupper())
        return words_list, caps_list

    def match_category(entity_set, threshold):
        q_words, q_caps = parse_query_words(text)
        candidates = []
        
        for entity in entity_set:
            entity_lower = entity.lower()
            entity_tokens = entity_lower.split()
            
            # Significant tokens
            sig_tokens = [t for t in entity_tokens if len(t) > threshold]
            if not sig_tokens:
                sig_tokens = [entity_lower]
                
            score = len(sig_tokens)
            
            # 1. Fast exact check with word boundaries
            if re.search(r'\b' + re.escape(entity_lower) + r'\b', text_lower):
                candidates.append((entity, score))
                continue
                
            # 2. Token match check
            # Require all significant tokens to be present in the query words
            if not all(t in q_words for t in sig_tokens):
                continue
                
            # Check other tokens (initials or skipped words) for contradiction
            contradiction = False
            for t in sig_tokens:
                # Find all occurrences of t in query words
                q_indices = [idx for idx, qw in enumerate(q_words) if qw == t]
                for q_idx in q_indices:
                    # Find index of t in entity tokens
                    try:
                        e_idx = entity_tokens.index(t)
                    except ValueError:
                        continue
                        
                    # Validate all other tokens in the entity relative to this matched token
                    for other_idx, other_token in enumerate(entity_tokens):
                        if other_idx == e_idx:
                            continue
                        offset = other_idx - e_idx
                        target_q_idx = q_idx + offset
                        
                        if 0 <= target_q_idx < len(q_words):
                            # Only treat as contradiction if the query word is a capitalized proper noun
                            if q_caps[target_q_idx]:
                                q_word = q_words[target_q_idx]
                                if len(other_token) == 1:  # Initial (e.g. 'v', 't')
                                    if not q_word.startswith(other_token):
                                        contradiction = True
                                        break
                                else:  # Full word
                                    if q_word != other_token:
                                        contradiction = True
                                        break
                    if contradiction:
                        break
                if contradiction:
                    break
                    
            if not contradiction:
                candidates.append((entity, score))
                
        if not candidates:
            return []
            
        max_score = max(score for _, score in candidates)
        # Keep candidates with the highest token score (longest matches)
        return [entity for entity, score in candidates if score == max_score]

    entities = {
        "people": match_category(KNOWN_PEOPLE, 2),
        "organizations": match_category(KNOWN_ORGANIZATIONS, 3),
        "places": match_category(KNOWN_PLACES, 4),
        "dates": [],
        "identifiers": []
    }
    
    # Match dates (years from 2008 to 2026, or YYYY-MM-DD format)
    years = re.findall(r'\b(200\d|201\d|202\d)\b', text)
    for y in years:
        entities["dates"].append(y)
    dates_found = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
    for d in dates_found:
        entities["dates"].append(d)

    # Match identifiers (e.g. 5-7 digit match IDs)
    ids = re.findall(r'\b(\d{5,7})\b', text)
    for i in ids:
        if i not in entities["dates"]:
            entities["identifiers"].append(i)

    # Deduplicate
    entities["dates"] = list(set(entities["dates"]))
    entities["identifiers"] = list(set(entities["identifiers"]))
    
    return entities

def get_session_context(session_id: str):
    if not session_id:
        return {
            "people": [],
            "organizations": [],
            "dates": [],
            "places": [],
            "identifiers": []
        }, "", []

    ledger = {
        "people": [],
        "organizations": [],
        "dates": [],
        "places": [],
        "identifiers": []
    }
    summary = ""
    hot_window = []
    cache_hit = False

    if use_redis:
        try:
            ledger_str = redis_client.get(f"session:{session_id}:ledger")
            summary_val = redis_client.get(f"session:{session_id}:summary")
            hot_window_strs = redis_client.lrange(f"session:{session_id}:hot_window", 0, -1)

            if ledger_str is not None or summary_val is not None or hot_window_strs:
                cache_hit = True
                if ledger_str:
                    try:
                        ledger_loaded = json.loads(ledger_str)
                        if isinstance(ledger_loaded, dict):
                            ledger = ledger_loaded
                    except Exception:
                        pass
                if summary_val:
                    summary = summary_val
                if hot_window_strs:
                    hot_window = [json.loads(m) for m in hot_window_strs]
        except Exception as e:
            write_log(f"[redis] Error reading context: {e}")

    if not cache_hit:
        # Load from SQLite
        state = get_session_state(session_id)
        if state:
            ledger_raw = state.get("ledger")
            if ledger_raw:
                try:
                    ledger_loaded = json.loads(ledger_raw)
                    if isinstance(ledger_loaded, dict):
                        ledger = ledger_loaded
                except Exception:
                    pass
            summary = state.get("summary") or ""
        else:
            summary = ""

        # Fetch last 10 messages (chronological order)
        hot_window = get_recent_messages(session_id, limit=10)

        # Warm up Redis
        if use_redis:
            try:
                redis_client.set(f"session:{session_id}:ledger", json.dumps(ledger), ex=7200)
                redis_client.set(f"session:{session_id}:summary", summary, ex=7200)
                if hot_window:
                    redis_client.delete(f"session:{session_id}:hot_window")
                    redis_client.rpush(f"session:{session_id}:hot_window", *[json.dumps(m) for m in hot_window])
                    redis_client.expire(f"session:{session_id}:hot_window", 7200)
            except Exception as e:
                write_log(f"[redis] Error warming cache: {e}")

    # Ensure ledger is structured dict even if it was parsed as a list in database/cache due to legacy runs
    if not isinstance(ledger, dict):
        ledger = {
            "people": [],
            "organizations": [],
            "dates": [],
            "places": [],
            "identifiers": []
        }

    return ledger, summary, hot_window

def save_chat_turn_to_redis(session_id: str, user_msg: str, assistant_msg: str):
    if not use_redis or not session_id:
        return
    try:
        user_turn = {"role": "user", "content": user_msg}
        ast_turn = {"role": "assistant", "content": assistant_msg}
        
        # Append to Redis list
        redis_client.rpush(f"session:{session_id}:hot_window", json.dumps(user_turn), json.dumps(ast_turn))
        
        # Enforce sliding expiry (2 hours = 7200s)
        redis_client.expire(f"session:{session_id}:hot_window", 7200)
        redis_client.expire(f"session:{session_id}:ledger", 7200)
        redis_client.expire(f"session:{session_id}:summary", 7200)
        
        # Check window size and pop oldest 2 turns if size > 10
        length = redis_client.llen(f"session:{session_id}:hot_window")
        if length > 10:
            msg1_str = redis_client.lpop(f"session:{session_id}:hot_window")
            msg2_str = redis_client.lpop(f"session:{session_id}:hot_window")
            
            if msg1_str and msg2_str:
                redis_client.rpush(f"session:{session_id}:pending_summarization", msg1_str, msg2_str)
                redis_client.expire(f"session:{session_id}:pending_summarization", 7200)
    except Exception as e:
        write_log(f"[redis] Error saving turn to cache: {e}")

def extract_entities_llm(question: str, history: str = None) -> dict:
    prompt = f"""You are an assistant that extracts structured cricket entities (player names, team names, match details) from text.
Analyze the user question and the optional history context. Identify any entities and group them into these categories:
- people: player names, umpire names, person references (e.g. "V Kohli", "RG Sharma")
- organizations: IPL team names or abbreviations (e.g. "Mumbai Indians", "RCB")
- dates: seasons, match dates, years (e.g. "2024", "2008")
- places: venue cities or stadium names (e.g. "Wankhede Stadium", "Mumbai")
- identifiers: match IDs or specific numbers (e.g. "335982")

User Question: "{question}"
History Context: {history or "None"}

Return a JSON object in exactly this format:
{{
  "people": [],
  "organizations": [],
  "dates": [],
  "places": [],
  "identifiers": []
}}

Output ONLY valid JSON:"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content.strip())
        return {
            "people": data.get("people", []) or [],
            "organizations": data.get("organizations", []) or [],
            "dates": data.get("dates", []) or [],
            "places": data.get("places", []) or [],
            "identifiers": data.get("identifiers", []) or []
        }
    except Exception as e:
        write_log(f"[ledger] LLM extraction error: {e}")
        return {
            "people": [],
            "organizations": [],
            "dates": [],
            "places": [],
            "identifiers": []
        }

def update_ledger(session_id: str, user_id: int, question: str, old_ledger: dict, history_str: str) -> dict:
    matched = extract_entities_rule_based(question)
    
    # Check if rule-based found any entity
    has_any = any(len(val) > 0 for val in matched.values())
    
    if not has_any:
        reference_words = ["he", "him", "his", "they", "them", "their", "it", "this", "that", "compare", "player", "team", "venue", "stadium", "year", "season", "match"]
        has_reference = any(w in question.lower().split() for w in reference_words)
        if has_reference:
            matched = extract_entities_llm(question, history_str)
            
    # Merge matched entities into new_ledger
    new_ledger = {}
    for key in ["people", "organizations", "dates", "places", "identifiers"]:
        old_list = old_ledger.get(key, []) if isinstance(old_ledger, dict) else []
        matched_list = matched.get(key, [])
        combined = list(set(old_list + matched_list))
        # Keep only the last 5 entities per category to prevent bloat
        new_ledger[key] = combined[-5:]
    
    if session_id:
        if use_redis:
            try:
                redis_client.set(f"session:{session_id}:ledger", json.dumps(new_ledger), ex=7200)
            except Exception as e:
                write_log(f"[redis] Error saving ledger: {e}")
        
        # Sync to SQLite
        summary = ""
        if use_redis:
            try:
                summary = redis_client.get(f"session:{session_id}:summary") or ""
            except Exception:
                pass
        try:
            save_session_state(session_id, user_id, json.dumps(new_ledger), summary)
        except Exception as e:
            write_log(f"[sqlite] Error saving session state: {e}")
            
    return new_ledger

def summarize_session_history(session_id: str, user_id: int):
    if not session_id:
        return
    try:
        old_summary = ""
        pending_strs = []
        
        if use_redis:
            old_summary = redis_client.get(f"session:{session_id}:summary") or ""
            pending_strs = redis_client.lrange(f"session:{session_id}:pending_summarization", 0, -1)
        
        if not pending_strs:
            return
            
        pending_messages = [json.loads(m) for m in pending_strs]
        
        formatted_messages = []
        for m in pending_messages:
            role = "User" if m["role"] == "user" else "Assistant"
            formatted_messages.append(f"{role}: {m['content']}")
        pending_text = "\n".join(formatted_messages)
        
        prompt = f"""You are an assistant summarizing a chat conversation about cricket statistics.
Condense the following new messages into a single prose summary, integrating it with the existing summary if provided.

Existing Summary:
"{old_summary}"

New Messages to summarize:
{pending_text}

Provide a concise updated summary in prose under 100 words summarizing the main players, teams, and stats discussed. Do not use JSON or bullet points. Just prose.

Updated Summary:"""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=200,
        )
        new_summary = response.choices[0].message.content.strip()
        
        if use_redis:
            redis_client.set(f"session:{session_id}:summary", new_summary, ex=7200)
            redis_client.delete(f"session:{session_id}:pending_summarization")
            
            ledger_str = redis_client.get(f"session:{session_id}:ledger")
            try:
                ledger = json.loads(ledger_str) if ledger_str else {}
            except Exception:
                ledger = {}
        else:
            ledger = {}
            
        save_session_state(session_id, user_id, json.dumps(ledger), new_summary)
        write_log(f"[summarization] Updated summary for session {session_id}.")
    except Exception as e:
        write_log(f"[summarization] Error during background summarization: {e}")

def run_summarization_thread(session_id: str, user_id: int):
    t = threading.Thread(target=summarize_session_history, args=(session_id, user_id))
    t.daemon = True
    t.start()

def check_and_trigger_summarization(session_id: str, user_id: int):
    if not use_redis or not session_id:
        return
    try:
        pending_len = redis_client.llen(f"session:{session_id}:pending_summarization")
        if pending_len >= 6:
            write_log(f"[summarization] Triggering summary for session {session_id} (pending size: {pending_len})")
            run_summarization_thread(session_id, user_id)
    except Exception as e:
        write_log(f"[redis] Error checking summarization queue: {e}")

def format_context_str(ledger: dict, summary: str, hot_window: list) -> str:
    parts = []
    if ledger and isinstance(ledger, dict):
        ledger_lines = []
        for category, items in ledger.items():
            if items:
                ledger_lines.append(f"- {category.capitalize()}: {', '.join(items)}")
        if ledger_lines:
            parts.append("=== SESSION CONTEXT (ENTITY LEDGER) ===\n" + "\n".join(ledger_lines))
    if summary:
        parts.append(f"=== CONVERSATION SUMMARY ===\n{summary}")
    if hot_window:
        history_lines = []
        for msg in hot_window:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content']}")
        parts.append("=== RECENT DIALOGUE (HOT WINDOW) ===\n" + "\n".join(history_lines))
    
    return "\n\n".join(parts) if parts else ""


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
                    "season":       {"type": "string", "description": "Optional. Specify the season year e.g. '2024'. Omit this property if not filtered by a specific season."},
                    "specific_stat": {"type": "string", "description": "Optional. If user asks for just one specific statistic (e.g. 'wickets', 'runs', 'economy', 'strike rate'). Omit this property if a full profile/statistics are requested."}
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
def route_question(question: str, context_str: str = None):
    system_content = (
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
    if context_str:
        system_content = f"{context_str}\n\nUse the session context above to resolve pronouns and identify implicit entities in the user question.\n\n{system_content}"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": system_content
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
def generate_answer(question: str, tool: str, comparison_type: str, columns: list, rows: list, context_str: str = None):
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

    context_prefix = f"{context_str}\n\n" if context_str else ""

    prompt = f"""You are a cricket analyst giving factual IPL insights.

{context_prefix}User asked: "{question}"
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

def ask(question: str, session_id: str = None, user_id: int = None) -> dict:
    start_time = time.time()
    tool_name = None
    args = None
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        # Load session context
        ledger, summary, hot_window = get_session_context(session_id)
        context_str = format_context_str(ledger, summary, hot_window)

        # Route the question with context
        tool_call, route_usage = route_question(question, context_str)
        tool_name = tool_call.function.name
        args      = json.loads(tool_call.function.arguments)

        if route_usage:
            total_input_tokens += getattr(route_usage, "prompt_tokens", 0)
            total_output_tokens += getattr(route_usage, "completion_tokens", 0)

        if tool_name == "general_chat":
            if context_str:
                prompt = f"""You are a helpful cricket intelligence assistant.
Answer the user's question directly and concisely.

{context_str}

User asked: "{question}"

Rules:
- Be helpful, conversational, and direct.
- Do not mention or generate SQL queries.
- If the user asks about the app, explain that this is a Cricket Intelligence App that allows querying IPL statistics, comparing players, and checking match records.
- Keep it under 100 words."""
            else:
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

            # Save turn to cache and update state
            if session_id:
                save_chat_turn_to_redis(session_id, question, answer)
                ledger = update_ledger(session_id, user_id, question, ledger, context_str)
                check_and_trigger_summarization(session_id, user_id)

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
        answer, ans_usage = generate_answer(question, tool_name, comparison_type, columns, rows, context_str)
        if ans_usage:
            total_input_tokens += getattr(ans_usage, "prompt_tokens", 0)
            total_output_tokens += getattr(ans_usage, "completion_tokens", 0)

        # Save turn to cache and update state
        if session_id:
            save_chat_turn_to_redis(session_id, question, answer)
            ledger = update_ledger(session_id, user_id, question, ledger, context_str)
            check_and_trigger_summarization(session_id, user_id)

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