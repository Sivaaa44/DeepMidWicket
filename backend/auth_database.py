import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            monthly_token_limit INTEGER DEFAULT 50000
        )
        """)
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
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            ledger TEXT,
            summary TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
        """)
        
        # Schema migration to add monthly_token_limit if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "monthly_token_limit" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN monthly_token_limit INTEGER DEFAULT 50000")
            
        # Schema migration to add missing columns and indices for sessions
        cursor.execute("PRAGMA table_info(sessions)")
        sessions_cols = [row[1] for row in cursor.fetchall()]
        if "anon_ip" not in sessions_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN anon_ip TEXT")
        if "title" not in sessions_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN title TEXT NOT NULL DEFAULT 'New Chat'")
        if "created_at" not in sessions_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN created_at TEXT")
        if "last_message_preview" not in sessions_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_message_preview TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_anon_ip ON sessions(anon_ip)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
            
        conn.commit()

# Run database initialisation
init_db()

def create_user(email, username, password_hash):
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
                (email, username, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return {
                "id": user_id,
                "email": email,
                "username": username,
                "is_active": 1,
                "monthly_token_limit": 50000
            }
        except sqlite3.IntegrityError as e:
            raise ValueError("Email or Username already exists.") from e

def get_user_by_email(email):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

def get_user_by_username(username):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None

def log_token_usage(user_id, question, tool_used, input_tokens, output_tokens, success=1, error_message=None, latency_ms=None, ip_address=None):
    total_tokens = input_tokens + output_tokens
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO token_usage 
            (user_id, question, tool_used, input_tokens, output_tokens, total_tokens, success, error_message, latency_ms, ip_address) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, question, tool_used, input_tokens, output_tokens, total_tokens, success, error_message, latency_ms, ip_address)
        )
        conn.commit()

def get_user_stats(user_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 
                COUNT(*) as total_questions, 
                COALESCE(SUM(total_tokens), 0) as total_tokens 
            FROM token_usage 
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()
        return {
            "total_questions": row["total_questions"] if row else 0,
            "total_tokens": row["total_tokens"] if row else 0
        }

def get_user_monthly_usage(user_id):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(total_tokens), 0) as monthly_usage
            FROM token_usage
            WHERE user_id = ? AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
            """,
            (user_id,)
        ).fetchone()
        return row["monthly_usage"] if row else 0

def check_user_limit(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT monthly_token_limit FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        limit = row["monthly_token_limit"] if row else 50000
    
    used = get_user_monthly_usage(user_id)
    remaining = max(0, limit - used)
    allowed = used < limit
    return {
        "allowed": allowed,
        "used": used,
        "limit": limit,
        "remaining": remaining
    }

def save_message(session_id: str, role: str, content: str, user_id=None, anon_ip=None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, title, user_id, anon_ip FROM sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()

        preview = content[:100] if content else ""

        if not session_row:
            # First message / new session creation
            initial_title = "New Chat"
            if role == "user" and content:
                clean_content = content.strip()
                initial_title = clean_content[:40].strip() + ("..." if len(clean_content) > 40 else "")
            
            cursor.execute(
                """
                INSERT INTO sessions (session_id, user_id, anon_ip, title, last_message_preview, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (session_id, user_id, anon_ip, initial_title, preview)
            )
        else:
            current_title = session_row["title"]
            curr_user = session_row["user_id"] or user_id
            curr_ip = session_row["anon_ip"] or anon_ip

            # Auto title if title is still 'New Chat' and user is sending message
            if (current_title == "New Chat" or not current_title) and role == "user" and content:
                clean_content = content.strip()
                current_title = clean_content[:40].strip() + ("..." if len(clean_content) > 40 else "")

            cursor.execute(
                """
                UPDATE sessions 
                SET user_id = ?, anon_ip = ?, title = ?, last_message_preview = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                """,
                (curr_user, curr_ip, current_title, preview, session_id)
            )

        cursor.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()

def get_recent_messages(session_id: str, limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, timestamp FROM messages 
            WHERE session_id = ? 
            ORDER BY timestamp DESC, id DESC LIMIT ?
            """,
            (session_id, limit)
        ).fetchall()
        # Return chronological order (oldest first)
        return [{"role": r["role"], "content": r["content"], "created_at": r["timestamp"]} for r in reversed(rows)]

def save_session_state(session_id: str, user_id: int, ledger: str, summary: str):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, ledger, summary, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id = COALESCE(excluded.user_id, sessions.user_id),
                ledger = excluded.ledger,
                summary = excluded.summary,
                updated_at = CURRENT_TIMESTAMP
            """,
            (session_id, user_id, ledger, summary)
        )
        conn.commit()

def get_session_state(session_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT session_id, user_id, anon_ip, title, created_at, updated_at, last_message_preview, ledger, summary FROM sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        return dict(row) if row else None

def get_user_sessions(user_id=None, anon_ip=None, limit: int = 20, offset: int = 0):
    with get_connection() as conn:
        if user_id is not None:
            rows = conn.execute(
                """
                SELECT session_id AS id, title, created_at, updated_at, last_message_preview
                FROM sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset)
            ).fetchall()
        elif anon_ip is not None:
            rows = conn.execute(
                """
                SELECT session_id AS id, title, created_at, updated_at, last_message_preview
                FROM sessions
                WHERE user_id IS NULL AND anon_ip = ?
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (anon_ip, limit, offset)
            ).fetchall()
        else:
            rows = []
        return [dict(r) for r in rows]

def update_session_title(session_id: str, title: str, user_id=None, anon_ip=None) -> bool:
    with get_connection() as conn:
        session = get_session_state(session_id)
        if not session:
            return False
        
        # Verify ownership
        if user_id is not None:
            if session["user_id"] != user_id:
                return False
        elif anon_ip is not None:
            if session["user_id"] is not None or session["anon_ip"] != anon_ip:
                return False
        else:
            return False

        conn.execute(
            "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (title.strip() or "New Chat", session_id)
        )
        conn.commit()
        return True

def delete_session_db(session_id: str, user_id=None, anon_ip=None) -> bool:
    with get_connection() as conn:
        session = get_session_state(session_id)
        if not session:
            return False
        
        # Verify ownership
        if user_id is not None:
            if session["user_id"] != user_id:
                return False
        elif anon_ip is not None:
            if session["user_id"] is not None or session["anon_ip"] != anon_ip:
                return False
        else:
            return False

        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        return True


