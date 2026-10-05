"""Admin monitoring API. Authenticated by an admin user's JWT (or the optional ADMIN_KEY header)."""
import os
import time
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import config
import memory
from auth import Identity, require_admin
from auth_database import get_connection, get_user_by_id, update_user

router = APIRouter(dependencies=[Depends(require_admin)])

ASK = "COALESCE(request_type, 'ask') = 'ask'"


def _percentile(sorted_values: list, pct: float):
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    return round(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo))


def _since(days: int) -> str:
    return f"-{days - 1} days"


@router.get("/overview")
def overview(days: int = Query(14, ge=1, le=90)):
    since = _since(days)
    with get_connection() as conn:
        totals = conn.execute(f"""
            SELECT
              (SELECT COUNT(*) FROM users) AS users,
              (SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', ?, 'start of day')) AS new_users,
              (SELECT COUNT(*) FROM sessions WHERE updated_at >= datetime('now', ?, 'start of day')) AS active_sessions,
              (SELECT COUNT(DISTINCT COALESCE(CAST(user_id AS TEXT), 'ip:' || ip_address)) FROM token_usage
                 WHERE {ASK} AND timestamp >= datetime('now', ?, 'start of day')) AS active_identities
        """, (since, since, since)).fetchone()

        period = conn.execute(f"""
            SELECT
              SUM(CASE WHEN {ASK} THEN 1 ELSE 0 END) AS questions,
              SUM(CASE WHEN {ASK} AND success = 0 THEN 1 ELSE 0 END) AS errors,
              COALESCE(SUM(total_tokens), 0) AS tokens,
              COALESCE(SUM(input_tokens), 0) AS input_tokens,
              COALESCE(SUM(output_tokens), 0) AS output_tokens,
              SUM(CASE WHEN {ASK} AND user_id IS NULL THEN 1 ELSE 0 END) AS guest_questions
            FROM token_usage WHERE timestamp >= datetime('now', ?, 'start of day')
        """, (since,)).fetchone()

        prev = conn.execute(f"""
            SELECT SUM(CASE WHEN {ASK} THEN 1 ELSE 0 END) AS questions, COALESCE(SUM(total_tokens), 0) AS tokens,
                   SUM(CASE WHEN {ASK} AND success = 0 THEN 1 ELSE 0 END) AS errors
            FROM token_usage
            WHERE timestamp >= datetime('now', ?, 'start of day') AND timestamp < datetime('now', ?, 'start of day')
        """, (_since(days * 2), since)).fetchone()

        daily_rows = conn.execute(f"""
            SELECT date(timestamp) AS day,
                   SUM(CASE WHEN {ASK} THEN 1 ELSE 0 END) AS questions,
                   SUM(CASE WHEN {ASK} AND success = 0 THEN 1 ELSE 0 END) AS errors,
                   COALESCE(SUM(total_tokens), 0) AS tokens,
                   COUNT(DISTINCT CASE WHEN {ASK} THEN COALESCE(CAST(user_id AS TEXT), 'ip:' || ip_address) END) AS active,
                   ROUND(AVG(CASE WHEN {ASK} THEN latency_ms END)) AS avg_latency_ms
            FROM token_usage WHERE timestamp >= datetime('now', ?, 'start of day')
            GROUP BY day ORDER BY day
        """, (since,)).fetchall()

        tools = conn.execute(f"""
            SELECT COALESCE(tool_used, 'unknown') AS tool, COUNT(*) AS count,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors,
                   COALESCE(SUM(total_tokens), 0) AS tokens, ROUND(AVG(latency_ms)) AS avg_latency_ms
            FROM token_usage WHERE {ASK} AND timestamp >= datetime('now', ?, 'start of day')
            GROUP BY tool ORDER BY count DESC
        """, (since,)).fetchall()

        latencies = sorted(r[0] for r in conn.execute(f"""
            SELECT latency_ms FROM token_usage
            WHERE {ASK} AND latency_ms IS NOT NULL AND timestamp >= datetime('now', ?, 'start of day')
        """, (since,)))

        error_codes = conn.execute(f"""
            SELECT CASE WHEN error_message LIKE '[%]%' THEN substr(error_message, 2, instr(error_message, ']') - 2)
                        ELSE 'other' END AS code, COUNT(*) AS count
            FROM token_usage WHERE {ASK} AND success = 0 AND timestamp >= datetime('now', ?, 'start of day')
            GROUP BY code ORDER BY count DESC
        """, (since,)).fetchall()

        top_users = conn.execute(f"""
            SELECT u.id, u.username, u.email, COUNT(*) AS questions, COALESCE(SUM(t.total_tokens), 0) AS tokens
            FROM token_usage t JOIN users u ON u.id = t.user_id
            WHERE t.timestamp >= datetime('now', ?, 'start of day')
            GROUP BY u.id ORDER BY tokens DESC LIMIT 5
        """, (since,)).fetchall()

    # Fill missing days so charts have a continuous x-axis.
    by_day = {r["day"]: dict(r) for r in daily_rows}
    start = date.today() - timedelta(days=days - 1)
    daily = []
    for i in range(days):
        d = (start + timedelta(days=i)).isoformat()
        daily.append(by_day.get(d, {"day": d, "questions": 0, "errors": 0, "tokens": 0, "active": 0, "avg_latency_ms": None}))

    questions = period["questions"] or 0
    errors = period["errors"] or 0
    return {
        "days": days,
        "kpis": {
            "users": totals["users"],
            "new_users": totals["new_users"],
            "active_identities": totals["active_identities"],
            "active_sessions": totals["active_sessions"],
            "questions": questions,
            "guest_questions": period["guest_questions"] or 0,
            "tokens": period["tokens"],
            "input_tokens": period["input_tokens"],
            "output_tokens": period["output_tokens"],
            "errors": errors,
            "success_rate": round((questions - errors) * 100.0 / questions, 1) if questions else None,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "tokens_per_question": round(period["tokens"] / questions) if questions else None,
        },
        "previous": {"questions": prev["questions"] or 0, "tokens": prev["tokens"] or 0, "errors": prev["errors"] or 0},
        "daily": daily,
        "tools": [dict(r) for r in tools],
        "error_codes": [dict(r) for r in error_codes],
        "top_users": [dict(r) for r in top_users],
    }


@router.get("/system")
def system_status():
    def size(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return None

    with get_connection() as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("users", "sessions", "messages", "message_artifacts", "token_usage")}
    from main import STARTED_AT  # late import: main imports this module
    return {
        "environment": config.ENVIRONMENT,
        "uptime_s": int(time.time() - STARTED_AT),
        "redis": memory.redis_status(),
        "llm": {"configured": bool(config.GROQ_API_KEY), "model": config.LLM_MODEL,
                "summary_model": config.LLM_FAST_MODEL, "timeout_s": config.LLM_TIMEOUT_SECONDS},
        "databases": {"cricket_db_bytes": size(config.CRICKET_DB_PATH), "users_db_bytes": size(config.USERS_DB_PATH)},
        "row_counts": counts,
        "limits": {
            "default_monthly_tokens": config.DEFAULT_MONTHLY_TOKEN_LIMIT,
            "anon_questions": config.ANON_QUERY_LIMIT,
            "anon_window_hours": config.ANON_WINDOW_HOURS,
            "hot_window_messages": config.HOT_WINDOW_MESSAGES,
            "summarize_batch": config.SUMMARIZE_BATCH_MESSAGES,
            "sql_max_rows": config.SQL_MAX_ROWS,
        },
    }


USER_COLUMNS = f"""
    u.id, u.email, u.username, u.created_at, u.last_login_at, u.is_active, COALESCE(u.is_admin, 0) AS is_admin,
    COALESCE(u.monthly_token_limit, {config.DEFAULT_MONTHLY_TOKEN_LIMIT}) AS monthly_token_limit,
    (SELECT COUNT(*) FROM token_usage t WHERE t.user_id = u.id AND {ASK.replace('request_type', 't.request_type')}) AS total_questions,
    (SELECT COALESCE(SUM(t.total_tokens), 0) FROM token_usage t WHERE t.user_id = u.id) AS total_tokens,
    (SELECT COALESCE(SUM(t.total_tokens), 0) FROM token_usage t
       WHERE t.user_id = u.id AND t.timestamp >= datetime('now', 'start of month')) AS monthly_usage,
    (SELECT COUNT(*) FROM sessions s WHERE s.user_id = u.id) AS sessions,
    (SELECT MAX(t.timestamp) FROM token_usage t WHERE t.user_id = u.id) AS last_active
"""

USER_SORTS = {"recent": "last_active DESC", "tokens": "monthly_usage DESC", "created": "u.created_at DESC",
              "questions": "total_questions DESC"}


@router.get("/users")
def list_users(
    q: str | None = Query(None, max_length=100),
    sort: str = Query("recent"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where, params = "", []
    if q:
        where = "WHERE u.email LIKE ? OR u.username LIKE ?"
        params = [f"%{q}%", f"%{q}%"]
    order = USER_SORTS.get(sort, USER_SORTS["recent"])
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM users u {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {USER_COLUMNS} FROM users u {where} ORDER BY {order}, u.id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    return {"total": total, "users": [dict(r) for r in rows]}


@router.get("/users/{user_id}")
def user_detail(user_id: int):
    with get_connection() as conn:
        row = conn.execute(f"SELECT {USER_COLUMNS} FROM users u WHERE u.id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        daily = conn.execute(f"""
            SELECT date(timestamp) AS day, COALESCE(SUM(total_tokens), 0) AS tokens,
                   SUM(CASE WHEN {ASK} THEN 1 ELSE 0 END) AS questions
            FROM token_usage WHERE user_id = ? AND timestamp >= datetime('now', '-29 days', 'start of day')
            GROUP BY day ORDER BY day
        """, (user_id,)).fetchall()
        recent = conn.execute(f"""
            SELECT id, question, tool_used, total_tokens, latency_ms, success, error_message, timestamp
            FROM token_usage WHERE user_id = ? AND {ASK} ORDER BY id DESC LIMIT 20
        """, (user_id,)).fetchall()
    return {"user": dict(row), "daily": [dict(r) for r in daily], "recent": [dict(r) for r in recent]}


class UserUpdate(BaseModel):
    monthly_token_limit: int | None = Field(None, ge=0, le=100_000_000)
    is_active: bool | None = None
    is_admin: bool | None = None


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserUpdate, admin: Identity = Depends(require_admin)):
    if not get_user_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if admin.user_id == user_id and (body.is_active is False or body.is_admin is False):
        raise HTTPException(status_code=400, detail="You can't deactivate or demote your own account.")
    update_user(
        user_id,
        monthly_token_limit=body.monthly_token_limit,
        is_active=None if body.is_active is None else int(body.is_active),
        is_admin=None if body.is_admin is None else int(body.is_admin),
    )
    return user_detail(user_id)["user"]


@router.get("/activity")
def activity(
    status_filter: str = Query("all", alias="status", pattern="^(all|success|error)$"),
    tool: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    clauses, params = [f"{ASK.replace('request_type', 't.request_type')}"], []
    if status_filter == "success":
        clauses.append("t.success = 1")
    elif status_filter == "error":
        clauses.append("t.success = 0")
    if tool:
        clauses.append("t.tool_used = ?")
        params.append(tool)
    if q:
        clauses.append("t.question LIKE ?")
        params.append(f"%{q}%")
    where = " AND ".join(clauses)
    with get_connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM token_usage t WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"""
            SELECT t.id, t.question, t.tool_used, t.user_id, u.username, t.ip_address, t.success, t.error_message,
                   t.input_tokens, t.output_tokens, t.total_tokens, t.latency_ms, t.session_id, t.timestamp
            FROM token_usage t LEFT JOIN users u ON u.id = t.user_id
            WHERE {where} ORDER BY t.id DESC LIMIT ? OFFSET ?
        """, (*params, limit, offset)).fetchall()
    return {"total": total, "items": [dict(r) for r in rows]}
