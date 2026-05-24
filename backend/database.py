import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "cricket.db")


def run_query(sql: str):
    """
    Runs a SELECT query against the cricket database.
    Returns (columns, rows) on success, raises Exception on failure.
    """
    cleaned = sql.strip().upper()
    if not cleaned.startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(50)
        columns = [desc[0] for desc in cursor.description]
        return columns, [dict(row) for row in rows]
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