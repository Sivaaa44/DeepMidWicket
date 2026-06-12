import os
import sqlite3
from datetime import date
from fastapi import APIRouter, HTTPException, Header, Depends, status

router = APIRouter()

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")
ADMIN_KEY = os.getenv("ADMIN_KEY", "dev-admin-key")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def require_admin(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    if not x_admin_key or x_admin_key != ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-Admin-Key"
        )

# helper to calculate next month's 1st date (reset date)
def get_reset_date():
    today = date.today()
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    return next_month.strftime("%Y-%m-%d")

@router.get("/stats")
def get_stats(admin_check: None = Depends(require_admin)):
    with get_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        new_users_today = conn.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')").fetchone()[0]
        new_users_this_week = conn.execute("SELECT COUNT(*) FROM users WHERE date(created_at) >= date('now', '-7 days')").fetchone()[0]
        
        total_questions_all_time = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()[0]
        total_questions_today = conn.execute("SELECT COUNT(*) FROM token_usage WHERE date(timestamp) = date('now')").fetchone()[0]
        total_tokens_all_time = conn.execute("SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage").fetchone()[0]
        
        success_rate = conn.execute(
            "SELECT ROUND(COALESCE(SUM(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100.0 / NULLIF(COUNT(*), 0), 100.0), 2) FROM token_usage"
        ).fetchone()[0]
        
        avg_latency_ms = conn.execute(
            "SELECT ROUND(COALESCE(AVG(latency_ms), 0.0), 2) FROM token_usage"
        ).fetchone()[0]
        
        tool_row = conn.execute(
            "SELECT tool_used, COUNT(*) as cnt FROM token_usage WHERE tool_used IS NOT NULL AND tool_used != 'unknown' GROUP BY tool_used ORDER BY cnt DESC LIMIT 1"
        ).fetchone()
        most_used_tool = tool_row["tool_used"] if tool_row else None
        
        return {
            "total_users": total_users,
            "new_users_today": new_users_today,
            "new_users_this_week": new_users_this_week,
            "total_questions_all_time": total_questions_all_time,
            "total_questions_today": total_questions_today,
            "total_tokens_all_time": total_tokens_all_time,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency_ms,
            "most_used_tool": most_used_tool
        }

@router.get("/users")
def get_users(admin_check: None = Depends(require_admin)):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT 
                u.id, 
                u.email, 
                u.username, 
                u.created_at, 
                u.is_active,
                u.monthly_token_limit,
                (SELECT COUNT(*) FROM token_usage t WHERE t.user_id = u.id) as total_questions,
                (SELECT COALESCE(SUM(t.total_tokens), 0) FROM token_usage t WHERE t.user_id = u.id) as total_tokens_used,
                (SELECT COALESCE(SUM(t.total_tokens), 0) FROM token_usage t WHERE t.user_id = u.id AND strftime('%Y-%m', t.timestamp) = strftime('%Y-%m', 'now')) as monthly_usage,
                (SELECT MAX(t.timestamp) FROM token_usage t WHERE t.user_id = u.id) as last_active
            FROM users u
        """).fetchall()
        
        users_list = []
        for row in rows:
            u_dict = dict(row)
            limit = u_dict.pop("monthly_token_limit", 50000)
            monthly_usage = u_dict.pop("monthly_usage", 0)
            u_dict["tokens_remaining"] = max(0, limit - monthly_usage)
            users_list.append(u_dict)
            
        return users_list

@router.get("/users/{user_id}")
def get_user_detail(user_id: int, admin_check: None = Depends(require_admin)):
    with get_connection() as conn:
        u_row = conn.execute("SELECT id, email, username, created_at, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
        if not u_row:
            raise HTTPException(status_code=404, detail="User not found")
        
        profile = dict(u_row)
        
        stats_row = conn.execute("""
            SELECT 
                COUNT(*) as total_questions,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(CASE WHEN strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now') THEN total_tokens ELSE 0 END), 0) as monthly_usage
            FROM token_usage
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        usage_stats = dict(stats_row)
        
        q_rows = conn.execute("""
            SELECT question, tool_used, total_tokens as tokens, latency_ms as latency, success, timestamp
            FROM token_usage
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        """, (user_id,)).fetchall()
        
        last_10_questions = [dict(r) for r in q_rows]
        
        return {
            "profile": profile,
            "usage_stats": usage_stats,
            "last_10_questions": last_10_questions
        }

@router.get("/questions")
def get_questions(admin_check: None = Depends(require_admin)):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT question, tool_used, user_id, success, latency_ms, timestamp
            FROM token_usage
            ORDER BY timestamp DESC
            LIMIT 50
        """).fetchall()
        return [dict(r) for r in rows]

@router.get("/errors")
def get_errors(admin_check: None = Depends(require_admin)):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT question, error_message, user_id, timestamp
            FROM token_usage
            WHERE success = 0
            ORDER BY timestamp DESC
            LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]
