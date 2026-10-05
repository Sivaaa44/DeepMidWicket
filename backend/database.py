import re
import sqlite3
import time

import config


class QueryError(Exception):
    """Raised when a generated query is rejected or fails to execute."""


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def clean_sql(sql: str) -> str:
    """Strip markdown fences, comments and trailing semicolons from LLM output."""
    text = re.sub(r"```(?:sql)?", "", sql or "", flags=re.IGNORECASE).strip()
    text = re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text.strip().rstrip(";").strip()


def validate_sql(sql: str) -> str:
    cleaned = clean_sql(sql)
    if not cleaned:
        raise QueryError("The generated query was empty.")
    head = cleaned.split(None, 1)[0].upper()
    if head not in ("SELECT", "WITH"):
        raise QueryError("Only SELECT queries are allowed.")
    if ";" in cleaned:
        raise QueryError("Only a single statement is allowed.")
    if _FORBIDDEN.search(cleaned):
        raise QueryError("The query contains a forbidden keyword.")
    return cleaned


def _connect_readonly() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{config.CRICKET_DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def run_query(sql: str, max_rows: int = None):
    """
    Run a validated, read-only SELECT against the cricket database.
    Returns (cleaned_sql, columns, rows). Raises QueryError on rejection or failure.
    """
    cleaned = validate_sql(sql)
    max_rows = max_rows or config.SQL_MAX_ROWS
    conn = _connect_readonly()
    deadline = time.monotonic() + config.SQL_TIMEOUT_SECONDS
    # Abort long-running queries (returning non-zero interrupts execution).
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cursor = conn.execute(cleaned)
        rows = cursor.fetchmany(max_rows)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return cleaned, columns, [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise QueryError(f"Query exceeded the {config.SQL_TIMEOUT_SECONDS:g}s time limit.") from e
        raise QueryError(str(e)) from e
    except sqlite3.Error as e:
        raise QueryError(str(e)) from e
    finally:
        conn.close()


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_deliveries_match ON deliveries(match_id)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_batter ON deliveries(batter)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_bowler ON deliveries(bowler)",
    "CREATE INDEX IF NOT EXISTS idx_matches_season_number ON matches(season, match_number)",
)


def ensure_indexes():
    """
    Create the indexes generated queries rely on (joins on match_id, finals lookups).
    Without them a finals query scans ~20s; with them it takes well under a second.
    Takes ~0.5s once; a no-op afterwards. Skipped quietly if the file is read-only.
    """
    try:
        conn = sqlite3.connect(config.CRICKET_DB_PATH)
        try:
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
            missing = [s for s in INDEXES if s.split()[5] not in existing]
            if missing:
                for statement in missing:
                    conn.execute(statement)
                conn.execute("ANALYZE")
                conn.commit()
            return len(missing)
        finally:
            conn.close()
    except sqlite3.Error as e:
        import logging
        logging.getLogger("database").warning("Could not create cricket.db indexes: %s", e)
        return 0


def get_known_entities():
    """Distinct people, teams and places, used for rule-based entity extraction."""
    conn = _connect_readonly()
    try:
        teams = {r[0].strip() for r in conn.execute(
            "SELECT team1 FROM matches UNION SELECT team2 FROM matches") if r[0]}
        people = {r[0].strip() for r in conn.execute(
            "SELECT batter FROM deliveries UNION SELECT bowler FROM deliveries "
            "UNION SELECT player_of_match FROM matches") if r[0]}
        places = {r[0].strip() for r in conn.execute(
            "SELECT venue FROM matches UNION SELECT city FROM matches") if r[0]}
        return people, teams, places
    finally:
        conn.close()


def get_dataset_summary() -> dict:
    conn = _connect_readonly()
    try:
        row = conn.execute(
            "SELECT COUNT(*), MIN(season), MAX(season), MIN(date), MAX(date) FROM matches"
        ).fetchone()
        deliveries = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        return {
            "matches": row[0], "first_season": row[1], "last_season": row[2],
            "first_date": row[3], "last_date": row[4], "deliveries": deliveries,
        }
    finally:
        conn.close()


def get_schema() -> str:
    return """
=== DATABASE SCHEMA ===

Table: matches (1 row per IPL match)
Columns:
  - match_id       : TEXT, primary key. Filename-based unique ID e.g. '335982'
  - season         : TEXT, IPL season e.g. '2008', '2023', '2024'. NOT a number, use quotes.
  - date           : TEXT, match date in 'YYYY-MM-DD' format
  - venue          : TEXT, full stadium name e.g. 'Wankhede Stadium', 'Eden Gardens'
  - city           : TEXT, city name e.g. 'Mumbai', 'Chennai', 'Kolkata'
  - event_name     : TEXT, always 'Indian Premier League' for IPL matches
  - match_number   : INTEGER, match number within the season. The FINAL is always the highest match_number in a season.
  - team1          : TEXT, one of the two teams (not necessarily batting first)
  - team2          : TEXT, the other team
  - toss_winner    : TEXT, team that won the toss
  - toss_decision  : TEXT, either 'bat' or 'field'
  - winner         : TEXT, team that won the match. NULL if no result.
  - win_by_runs    : INTEGER, runs margin if won batting first. NULL if won by wickets.
  - win_by_wickets : INTEGER, wickets margin if won chasing. NULL if won by runs.
  - player_of_match: TEXT, player name e.g. 'V Kohli', 'RG Sharma'
  - gender         : TEXT, always 'male' in this dataset
  - match_type     : TEXT, always 'T20' in this dataset

Table: deliveries (1 row per ball bowled)
Columns:
  - id             : INTEGER, auto-increment primary key
  - match_id       : TEXT, foreign key to matches.match_id
  - innings        : INTEGER, 1 = first innings, 2 = second innings (chase)
  - batting_team   : TEXT, team currently batting
  - bowling_team   : TEXT, team currently bowling
  - over           : INTEGER, 0-indexed. over=0 means first over, over=19 means last over.
  - ball           : INTEGER, ball number within the over (1-indexed, can exceed 6 for extras)
  - batter         : TEXT, current striker. Names use initials e.g. 'V Kohli', 'RG Sharma', 'MS Dhoni'
  - non_striker    : TEXT, non-striking batter
  - bowler         : TEXT, bowler name in same initials format
  - runs_batter    : INTEGER, runs scored off the bat (0-6). Does NOT include extras.
  - runs_extras    : INTEGER, extra runs on this ball
  - runs_total     : INTEGER, total runs on this ball = runs_batter + runs_extras
  - extras_type    : TEXT, 'wides', 'noballs', 'legbyes', 'byes', or NULL if no extra
  - is_wicket      : INTEGER, 1 if wicket fell, 0 otherwise
  - wicket_kind    : TEXT, 'caught', 'bowled', 'lbw', 'run out', 'stumped'. NULL if no wicket.
  - player_out     : TEXT, name of dismissed player. NULL if no wicket.

=== CRICKET CALCULATION RULES ===

STRIKE RATE (batter):
  ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)

ECONOMY RATE (bowler):
  ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2)
  -- NEVER use SUM(over) to calculate overs bowled

PHASE FILTERS:
  Powerplay  = over BETWEEN 0 AND 5
  Middle     = over BETWEEN 6 AND 14
  Death      = over BETWEEN 15 AND 19

FINALS FILTER:
  WHERE m.match_number = (SELECT MAX(match_number) FROM matches m2 WHERE m2.season = m.season)

PLAYER NAME SEARCH:
  Always use LIKE '%keyword%'
  Common names: Rohit = 'RG Sharma', Dhoni = 'MS Dhoni', Kohli = 'V Kohli',
  Bumrah = 'JJ Bumrah', Malinga = 'SL Malinga', Warner = 'DA Warner'

MINIMUM THRESHOLDS (always apply for ranking queries):
  Batters  : HAVING COUNT(CASE WHEN extras_type != 'wides' THEN 1 END) >= 200
  Bowlers  : HAVING COUNT(CASE WHEN extras_type != 'wides' THEN 1 END) >= 300

=== VERIFIED EXAMPLE QUERIES ===

Q: Who has scored the most runs in IPL history?
SQL:
SELECT batter AS player, SUM(runs_batter) AS total_runs,
  COUNT(DISTINCT match_id) AS matches,
  ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2) AS strike_rate
FROM deliveries
GROUP BY batter
ORDER BY total_runs DESC
LIMIT 10;

Q: Best economy bowlers in IPL history (min 300 balls)?
SQL:
SELECT bowler AS player,
  COUNT(DISTINCT match_id) AS matches,
  ROUND(SUM(runs_total) * 6.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2) AS economy,
  SUM(is_wicket) AS wickets
FROM deliveries
GROUP BY bowler
HAVING COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END) >= 300
ORDER BY economy ASC
LIMIT 10;

Q: Compare Kohli and Rohit Sharma in death overs?
SQL:
SELECT
  CASE WHEN batter LIKE '%Kohli%' THEN 'V Kohli' ELSE 'RG Sharma' END AS player,
  SUM(runs_batter) AS runs,
  COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END) AS balls_faced,
  ROUND(SUM(runs_batter) * 100.0 / COUNT(CASE WHEN extras_type IS NULL OR extras_type != 'wides' THEN 1 END), 2) AS strike_rate,
  SUM(is_wicket) AS dismissals
FROM deliveries
WHERE over BETWEEN 15 AND 19
  AND (batter LIKE '%Kohli%' OR batter LIKE '%RG Sharma%')
GROUP BY CASE WHEN batter LIKE '%Kohli%' THEN 'V Kohli' ELSE 'RG Sharma' END;

Q: Which team wins most after winning the toss?
SQL:
SELECT toss_winner AS team,
  COUNT(*) AS toss_wins,
  SUM(CASE WHEN toss_winner = winner THEN 1 ELSE 0 END) AS match_wins_after_toss,
  ROUND(SUM(CASE WHEN toss_winner = winner THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS win_percentage
FROM matches
WHERE winner IS NOT NULL
GROUP BY toss_winner
ORDER BY win_percentage DESC
LIMIT 10;

Q: Most sixes hit in a single season?
SQL:
SELECT m.season, d.batting_team AS team,
  SUM(CASE WHEN d.runs_batter = 6 THEN 1 ELSE 0 END) AS sixes
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
GROUP BY m.season, d.batting_team
ORDER BY sixes DESC
LIMIT 10;

Q: Best economy bowlers in IPL finals?
SQL:
SELECT d.bowler AS player,
  COUNT(DISTINCT d.match_id) AS finals_played,
  SUM(d.is_wicket) AS wickets,
  ROUND(SUM(d.runs_total) * 6.0 / COUNT(CASE WHEN d.extras_type IS NULL OR d.extras_type != 'wides' THEN 1 END), 2) AS economy
FROM deliveries d
JOIN matches m ON d.match_id = m.match_id
WHERE m.match_number = (SELECT MAX(match_number) FROM matches m2 WHERE m2.season = m.season)
GROUP BY d.bowler
HAVING COUNT(DISTINCT d.match_id) >= 2
ORDER BY economy ASC
LIMIT 10;
"""