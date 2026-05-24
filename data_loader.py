import json
import sqlite3
import os
import glob

# ── Config ──────────────────────────────────────────────────────────────────
JSON_FOLDER = "./ipl_json"   # ← change this to wherever your JSON files are
DB_PATH     = "./cricket.db"
# ────────────────────────────────────────────────────────────────────────────

def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id        TEXT PRIMARY KEY,
            season          TEXT,
            date            TEXT,
            venue           TEXT,
            city            TEXT,
            event_name      TEXT,
            match_number    INTEGER,
            team1           TEXT,
            team2           TEXT,
            toss_winner     TEXT,
            toss_decision   TEXT,
            winner          TEXT,
            win_by_runs     INTEGER,
            win_by_wickets  INTEGER,
            player_of_match TEXT,
            gender          TEXT,
            match_type      TEXT
        );

        CREATE TABLE IF NOT EXISTS deliveries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id        TEXT,
            innings         INTEGER,
            batting_team    TEXT,
            bowling_team    TEXT,
            over            INTEGER,
            ball            INTEGER,
            batter          TEXT,
            non_striker     TEXT,
            bowler          TEXT,
            runs_batter     INTEGER,
            runs_extras     INTEGER,
            runs_total      INTEGER,
            extras_type     TEXT,
            is_wicket       INTEGER DEFAULT 0,
            wicket_kind     TEXT,
            player_out      TEXT,
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        );
    """)
    conn.commit()


def parse_match(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)

    info = data.get("info", {})

    # Use filename (without extension) as match_id
    match_id = os.path.splitext(os.path.basename(filepath))[0]

    # Match-level info
    teams = info.get("teams", [None, None])
    outcome = info.get("outcome", {})
    by = outcome.get("by", {})
    dates = info.get("dates", [""])
    event = info.get("event", {})
    toss = info.get("toss", {})
    pom = info.get("player_of_match", [])

    match_row = {
        "match_id":        match_id,
        "season":          info.get("season"),
        "date":            dates[0] if dates else None,
        "venue":           info.get("venue"),
        "city":            info.get("city"),
        "event_name":      event.get("name"),
        "match_number":    event.get("match_number"),
        "team1":           teams[0] if len(teams) > 0 else None,
        "team2":           teams[1] if len(teams) > 1 else None,
        "toss_winner":     toss.get("winner"),
        "toss_decision":   toss.get("decision"),
        "winner":          outcome.get("winner"),
        "win_by_runs":     by.get("runs"),
        "win_by_wickets":  by.get("wickets"),
        "player_of_match": ", ".join(pom) if pom else None,
        "gender":          info.get("gender"),
        "match_type":      info.get("match_type"),
    }

    # Delivery-level info
    delivery_rows = []
    innings_data = data.get("innings", [])

    for innings_idx, innings in enumerate(innings_data):
        batting_team = innings.get("team")
        # Figure out bowling team
        all_teams = list(info.get("players", {}).keys())
        bowling_team = next((t for t in all_teams if t != batting_team), None)

        for over_data in innings.get("overs", []):
            over_num = over_data.get("over")
            for ball_idx, delivery in enumerate(over_data.get("deliveries", [])):
                runs = delivery.get("runs", {})
                extras = delivery.get("extras", {})
                wickets = delivery.get("wickets", [])

                is_wicket = 1 if wickets else 0
                wicket_kind = wickets[0].get("kind") if wickets else None
                player_out = wickets[0].get("player_out") if wickets else None
                extras_type = ", ".join(extras.keys()) if extras else None

                delivery_rows.append({
                    "match_id":     match_id,
                    "innings":      innings_idx + 1,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "over":         over_num,
                    "ball":         ball_idx + 1,
                    "batter":       delivery.get("batter"),
                    "non_striker":  delivery.get("non_striker"),
                    "bowler":       delivery.get("bowler"),
                    "runs_batter":  runs.get("batter", 0),
                    "runs_extras":  runs.get("extras", 0),
                    "runs_total":   runs.get("total", 0),
                    "extras_type":  extras_type,
                    "is_wicket":    is_wicket,
                    "wicket_kind":  wicket_kind,
                    "player_out":   player_out,
                })

    return match_row, delivery_rows


def load_all(conn):
    files = glob.glob(os.path.join(JSON_FOLDER, "*.json"))
    print(f"Found {len(files)} match files")

    match_insert = """
        INSERT OR IGNORE INTO matches VALUES (
            :match_id, :season, :date, :venue, :city, :event_name,
            :match_number, :team1, :team2, :toss_winner, :toss_decision,
            :winner, :win_by_runs, :win_by_wickets, :player_of_match,
            :gender, :match_type
        )
    """
    delivery_insert = """
        INSERT INTO deliveries (
            match_id, innings, batting_team, bowling_team, over, ball,
            batter, non_striker, bowler, runs_batter, runs_extras,
            runs_total, extras_type, is_wicket, wicket_kind, player_out
        ) VALUES (
            :match_id, :innings, :batting_team, :bowling_team, :over, :ball,
            :batter, :non_striker, :bowler, :runs_batter, :runs_extras,
            :runs_total, :extras_type, :is_wicket, :wicket_kind, :player_out
        )
    """

    for i, filepath in enumerate(files):
        try:
            match_row, delivery_rows = parse_match(filepath)
            conn.execute(match_insert, match_row)
            conn.executemany(delivery_insert, delivery_rows)
            if (i + 1) % 100 == 0:
                print(f"  Loaded {i + 1}/{len(files)} matches...")
        except Exception as e:
            print(f"  Error on {filepath}: {e}")

    conn.commit()
    print("Done!")


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)
    load_all(conn)

    # Quick sanity check
    matches_count  = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    delivery_count = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
    print(f"\nmatches:    {matches_count}")
    print(f"deliveries: {delivery_count}")

    conn.close()