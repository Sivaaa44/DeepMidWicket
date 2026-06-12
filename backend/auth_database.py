import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
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
        
        # Schema migration to add monthly_token_limit if it doesn't exist
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "monthly_token_limit" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN monthly_token_limit INTEGER DEFAULT 50000")
            
        # Schema migration to add new columns to token_usage if they don't exist
        cursor.execute("PRAGMA table_info(token_usage)")
        token_usage_cols = [row[1] for row in cursor.fetchall()]
        if "success" not in token_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN success INTEGER DEFAULT 1")
        if "error_message" not in token_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN error_message TEXT")
        if "latency_ms" not in token_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN latency_ms INTEGER")
        if "ip_address" not in token_usage_cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN ip_address TEXT")
            
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
