"""Application database: users, usage accounting, chat sessions and message artifacts."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone

import config


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.USERS_DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    """UTC timestamp in the same format SQLite's CURRENT_TIMESTAMP produces."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn, table: str, column: str, ddl: str):
    if column not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db():
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            monthly_token_limit INTEGER
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            question TEXT,
            tool_used TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            total_tokens INTEGER,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            latency_ms INTEGER,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            ledger TEXT,
            summary TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS message_artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            tool TEXT,
            args TEXT,
            sql_query TEXT,
            result_columns TEXT,
            result_rows TEXT,
            row_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
        )""")

        # Migrations for databases created by earlier versions.
        _add_column(conn, "users", "monthly_token_limit", "INTEGER")
        _add_column(conn, "users", "is_admin", "INTEGER DEFAULT 0")
        _add_column(conn, "users", "last_login_at", "TEXT")
        _add_column(conn, "token_usage", "request_type", "TEXT DEFAULT 'ask'")
        _add_column(conn, "token_usage", "session_id", "TEXT")
        _add_column(conn, "sessions", "anon_ip", "TEXT")
        _add_column(conn, "sessions", "title", "TEXT NOT NULL DEFAULT 'New Chat'")
        _add_column(conn, "sessions", "created_at", "TEXT")
        _add_column(conn, "sessions", "last_message_preview", "TEXT")
        _add_column(conn, "sessions", "summarized_upto", "INTEGER DEFAULT 0")
        _add_column(conn, "messages", "is_error", "INTEGER DEFAULT 0")

        conn.execute("UPDATE sessions SET created_at = updated_at WHERE created_at IS NULL")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_anon_ip ON sessions(anon_ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_message ON message_artifacts(message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_time ON token_usage(user_id, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_ip_time ON token_usage(ip_address, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_time ON token_usage(timestamp)")

        if config.ADMIN_EMAILS:
            placeholders = ",".join("?" * len(config.ADMIN_EMAILS))
            conn.execute(
                f"UPDATE users SET is_admin = 1 WHERE lower(email) IN ({placeholders})",
                tuple(config.ADMIN_EMAILS),
            )


init_db()


# ── Users ────────────────────────────────────────────────────────────────────

def _user_dict(row) -> dict | None:
    if not row:
        return None
    user = dict(row)
    if user.get("monthly_token_limit") is None:
        user["monthly_token_limit"] = config.DEFAULT_MONTHLY_TOKEN_LIMIT
    user["is_admin"] = bool(user.get("is_admin")) or user["email"].lower() in config.ADMIN_EMAILS
    user["is_active"] = bool(user.get("is_active", 1))
    return user


def create_user(email, username, password_hash):
    is_admin = 1 if email.lower() in config.ADMIN_EMAILS else 0
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (email, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
                (email, username, password_hash, is_admin, _now()),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError("Email or username already exists.") from e
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _user_dict(row)


def get_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
        return _user_dict(row)


def get_user_by_id(user_id):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_dict(row)


def get_user_by_username(username):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(username) = lower(?)", (username,)).fetchone()
        return _user_dict(row)


def touch_last_login(user_id: int):
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_now(), user_id))


def update_user(user_id: int, **fields) -> dict | None:
    allowed = {"monthly_token_limit", "is_active", "is_admin"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if updates:
        assignments = ", ".join(f"{k} = ?" for k in updates)
        with get_connection() as conn:
            conn.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*updates.values(), user_id))
    return get_user_by_id(user_id)


# ── Usage accounting ─────────────────────────────────────────────────────────

def log_token_usage(user_id, question, tool_used, input_tokens, output_tokens, success=1,
                    error_message=None, latency_ms=None, ip_address=None,
                    request_type="ask", session_id=None):
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO token_usage
            (user_id, question, tool_used, input_tokens, output_tokens, total_tokens, success,
             error_message, latency_ms, ip_address, request_type, session_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, question, tool_used, input_tokens or 0, output_tokens or 0, total_tokens,
             int(bool(success)), error_message, latency_ms, ip_address, request_type, session_id, _now()),
        )


def get_user_stats(user_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN COALESCE(request_type, 'ask') = 'ask' THEN 1 ELSE 0 END) AS total_questions,
                COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM token_usage WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        sessions = conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)).fetchone()[0]
        daily = conn.execute(
            """
            SELECT date(timestamp) AS day, COALESCE(SUM(total_tokens), 0) AS tokens,
                   SUM(CASE WHEN COALESCE(request_type, 'ask') = 'ask' THEN 1 ELSE 0 END) AS questions
            FROM token_usage
            WHERE user_id = ? AND timestamp >= datetime('now', '-29 days', 'start of day')
            GROUP BY day ORDER BY day
            """,
            (user_id,),
        ).fetchall()
        return {
            "total_questions": row["total_questions"] or 0,
            "total_tokens": row["total_tokens"] or 0,
            "total_sessions": sessions,
            "daily": [dict(r) for r in daily],
        }


def get_user_monthly_usage(user_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(total_tokens), 0) AS monthly_usage
            FROM token_usage
            WHERE user_id = ? AND timestamp >= datetime('now', 'start of month')
            """,
            (user_id,),
        ).fetchone()
        return row["monthly_usage"]


def next_reset_date() -> str:
    today = date.today()
    nxt = date(today.year + 1, 1, 1) if today.month == 12 else date(today.year, today.month + 1, 1)
    return nxt.isoformat()


def check_user_limit(user_id):
    user = get_user_by_id(user_id)
    limit = user["monthly_token_limit"] if user else config.DEFAULT_MONTHLY_TOKEN_LIMIT
    used = get_user_monthly_usage(user_id)
    return {
        "kind": "tokens",
        "allowed": used < limit,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "reset_date": next_reset_date(),
    }


def check_anon_limit(ip_address: str):
    """Anonymous users get a fixed number of questions per rolling window, keyed by IP."""
    with get_connection() as conn:
        used = conn.execute(
            """
            SELECT COUNT(*) FROM token_usage
            WHERE user_id IS NULL AND ip_address = ?
              AND COALESCE(request_type, 'ask') = 'ask'
              AND (success = 1 OR total_tokens > 0)  -- failures that cost nothing aren't charged
              AND timestamp >= datetime('now', ?)
            """,
            (ip_address, f"-{config.ANON_WINDOW_HOURS} hours"),
        ).fetchone()[0]
    limit = config.ANON_QUERY_LIMIT
    return {
        "kind": "questions",
        "allowed": used < limit,
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "window_hours": config.ANON_WINDOW_HOURS,
    }


# ── Sessions & messages ──────────────────────────────────────────────────────

def make_title(text: str) -> str:
    clean = " ".join((text or "").split())
    limit = 48
    return clean if len(clean) <= limit else clean[:limit].rstrip() + "…"


def _ensure_session(conn, session_id, user_id, anon_ip, first_question=None):
    row = conn.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    now = _now()
    if not row:
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, anon_ip, title, created_at, updated_at, summarized_upto)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (session_id, user_id, None if user_id else anon_ip,
             make_title(first_question) if first_question else "New Chat", now, now),
        )


def save_turn(session_id: str, question: str, result: dict, user_id=None, anon_ip=None) -> dict:
    """
    Persist one user question and its assistant answer (plus the result snapshot) in a
    single transaction, so the history never contains half a turn.
    """
    answer = result.get("answer") or ""
    error = result.get("error")
    data = result.get("data") or {}
    with get_connection() as conn:
        _ensure_session(conn, session_id, user_id, anon_ip, first_question=question)
        now = _now()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
            (session_id, question, now),
        )
        cursor = conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, is_error) VALUES (?, 'assistant', ?, ?, ?)",
            (session_id, answer if not error else (error.get("message") or answer), now, 1 if error else 0),
        )
        assistant_id = cursor.lastrowid

        rows = data.get("rows") or []
        cols = data.get("columns") or []
        if result.get("tool") or result.get("sql") or cols:
            conn.execute(
                """
                INSERT INTO message_artifacts
                (message_id, tool, args, sql_query, result_columns, result_rows, row_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (assistant_id, result.get("tool"),
                 json.dumps(result.get("args")) if result.get("args") is not None else None,
                 result.get("sql"),
                 json.dumps(cols) if cols else None,
                 json.dumps(rows[:config.ARTIFACT_MAX_ROWS], default=str) if rows else None,
                 len(rows), now),
            )

        preview = (answer if not error else question)[:140]
        conn.execute(
            """
            UPDATE sessions
            SET title = CASE WHEN title IS NULL OR title = '' OR title = 'New Chat' THEN ? ELSE title END,
                last_message_preview = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (make_title(question), preview, now, session_id),
        )
        return {"assistant_message_id": assistant_id}


def save_message(session_id: str, role: str, content: str, user_id=None, anon_ip=None,
                 tool: str = None, args: dict = None, sql: str = None, data: dict = None):
    """Single-message write kept for scripts and tests; the API uses save_turn."""
    with get_connection() as conn:
        _ensure_session(conn, session_id, user_id, anon_ip,
                        first_question=content if role == "user" else None)
        now = _now()
        cursor = conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now),
        )
        if role == "assistant" and (tool or sql or (isinstance(data, dict) and data)):
            cols = (data or {}).get("columns") or []
            rows = (data or {}).get("rows") or []
            conn.execute(
                """
                INSERT INTO message_artifacts
                (message_id, tool, args, sql_query, result_columns, result_rows, row_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cursor.lastrowid, tool, json.dumps(args) if args is not None else None, sql,
                 json.dumps(cols) if cols else None,
                 json.dumps(rows[:config.ARTIFACT_MAX_ROWS], default=str) if rows else None,
                 len(rows), now),
            )
        conn.execute(
            """
            UPDATE sessions
            SET title = CASE WHEN (title IS NULL OR title = '' OR title = 'New Chat') AND ? = 'user' THEN ? ELSE title END,
                last_message_preview = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (role, make_title(content), (content or "")[:140], now, session_id),
        )


def _json_or(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _message_dict(r) -> dict:
    msg = {
        "id": r["id"],
        "role": r["role"],
        "content": r["content"],
        "created_at": r["timestamp"],
    }
    if r["role"] == "assistant":
        msg["is_error"] = bool(r["is_error"])
        msg["tool"] = r["tool"]
        msg["sql"] = r["sql_query"]
        msg["args"] = _json_or(r["args"], {})
        msg["data"] = {
            "columns": _json_or(r["result_columns"], []),
            "rows": _json_or(r["result_rows"], []),
            "row_count": r["row_count"] or 0,
        }
    return msg


_MESSAGE_SELECT = """
    SELECT m.id, m.role, m.content, m.timestamp, COALESCE(m.is_error, 0) AS is_error,
           a.tool, a.args, a.sql_query, a.result_columns, a.result_rows, a.row_count
    FROM messages m
    LEFT JOIN message_artifacts a ON m.id = a.message_id
"""


def get_recent_messages(session_id: str, limit: int = 50, include_errors: bool = True):
    """Most recent `limit` messages of a session, returned in chronological order."""
    error_filter = "" if include_errors else "AND COALESCE(m.is_error, 0) = 0"
    with get_connection() as conn:
        rows = conn.execute(
            f"""{_MESSAGE_SELECT}
            WHERE m.session_id = ? {error_filter}
            ORDER BY m.id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
    return [_message_dict(r) for r in reversed(rows)]


def get_context_messages(session_id: str, limit: int):
    """
    Lightweight hot-window read for prompting: successful turns only, so a failed
    answer never pollutes the model's context. A failed turn drops both of its messages.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, COALESCE(is_error, 0) AS is_error
            FROM messages WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit * 2),
        ).fetchall()
    chronological = list(reversed(rows))
    cleaned = []
    for i, r in enumerate(chronological):
        if r["is_error"]:
            continue
        if r["role"] == "user" and i + 1 < len(chronological) and chronological[i + 1]["is_error"]:
            continue
        cleaned.append({"id": r["id"], "role": r["role"], "content": r["content"]})
    return cleaned[-limit:]


def get_unsummarized_messages(session_id: str, before_id: int):
    """Successful messages older than the hot window that have not been folded into the summary."""
    with get_connection() as conn:
        state = conn.execute(
            "SELECT COALESCE(summarized_upto, 0) FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        upto = state[0] if state else 0
        rows = conn.execute(
            """
            SELECT id, role, content FROM messages
            WHERE session_id = ? AND id > ? AND id < ? AND COALESCE(is_error, 0) = 0
            ORDER BY id
            """,
            (session_id, upto, before_id),
        ).fetchall()
        return [dict(r) for r in rows]


def save_session_memory(session_id: str, ledger: dict = None, summary: str = None, summarized_upto: int = None):
    """Update only the memory fields that were provided; never clobber the others."""
    fields, values = [], []
    if ledger is not None:
        fields.append("ledger = ?")
        values.append(json.dumps(ledger))
    if summary is not None:
        fields.append("summary = ?")
        values.append(summary)
    if summarized_upto is not None:
        fields.append("summarized_upto = MAX(COALESCE(summarized_upto, 0), ?)")
        values.append(summarized_upto)
    if not fields:
        return
    with get_connection() as conn:
        conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?", (*values, session_id))


def get_session_state(session_id: str):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT session_id, user_id, anon_ip, title, created_at, updated_at, last_message_preview,
                   ledger, summary, COALESCE(summarized_upto, 0) AS summarized_upto
            FROM sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        return dict(row) if row else None


def can_access_session(state: dict, user_id=None, anon_ip=None) -> bool:
    if state is None:
        return False
    if state.get("user_id") is not None:
        return user_id is not None and state["user_id"] == user_id
    return user_id is None and anon_ip is not None and state.get("anon_ip") == anon_ip


def get_user_sessions(user_id=None, anon_ip=None, limit: int = 20, offset: int = 0, search: str = None):
    if user_id is None and anon_ip is None:
        return []
    owner_sql = "s.user_id = ?" if user_id is not None else "s.user_id IS NULL AND s.anon_ip = ?"
    params = [user_id if user_id is not None else anon_ip]
    search_sql = ""
    if search:
        search_sql = "AND (s.title LIKE ? OR s.last_message_preview LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT s.session_id AS id, s.title, s.created_at, s.updated_at, s.last_message_preview,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user') AS turns
            FROM sessions s
            WHERE {owner_sql} {search_sql}
              AND EXISTS (SELECT 1 FROM messages m WHERE m.session_id = s.session_id)
            ORDER BY s.updated_at DESC, s.rowid DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def update_session_title(session_id: str, title: str, user_id=None, anon_ip=None) -> bool:
    state = get_session_state(session_id)
    if not can_access_session(state, user_id, anon_ip):
        return False
    clean = " ".join(title.split())[:config.SESSION_TITLE_MAX_LENGTH] or "New Chat"
    with get_connection() as conn:
        conn.execute("UPDATE sessions SET title = ? WHERE session_id = ?", (clean, session_id))
    return True


def delete_session_db(session_id: str, user_id=None, anon_ip=None) -> bool:
    state = get_session_state(session_id)
    if not can_access_session(state, user_id, anon_ip):
        return False
    with get_connection() as conn:
        # Artifacts cascade from messages via ON DELETE CASCADE.
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    return True
