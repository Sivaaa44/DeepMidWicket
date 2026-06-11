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
            is_active INTEGER DEFAULT 1
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
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
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
                "is_active": 1
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

def log_token_usage(user_id, question, tool_used, input_tokens, output_tokens):
    total_tokens = input_tokens + output_tokens
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO token_usage 
            (user_id, question, tool_used, input_tokens, output_tokens, total_tokens) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, question, tool_used, input_tokens, output_tokens, total_tokens)
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
