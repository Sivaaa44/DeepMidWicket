import json
import logging
import queue
import re
import threading
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import agent
import config
import memory
from admin_routes import router as admin_router
from auth import Identity, get_identity
from auth_database import (
    can_access_session, check_anon_limit, check_user_limit, delete_session_db, get_recent_messages,
    get_session_state, get_user_sessions, log_token_usage, save_turn, update_session_title,
)
from auth_routes import router as auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("api")

STARTED_AT = time.time()

app = FastAPI(title="DeepMidWicket — Cricket Intelligence API")
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key"],
)

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_LENGTH)
    session_id: str | None = None


class RenameSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def _session_or_404(session_id: str, identity: Identity) -> dict:
    state = get_session_state(session_id)
    if not state or not can_access_session(state, identity.user_id, identity.anon_ip):
        # Same response for "missing" and "not yours" so IDs can't be probed.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return state


def current_quota(identity: Identity) -> dict:
    if identity.user:
        return {"authenticated": True, **check_user_limit(identity.user_id)}
    return {"authenticated": False, **check_anon_limit(identity.ip)}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "service": "deepmidwicket"}


@app.get("/health")
def health():
    checks = {"redis": memory.redis_status(), "llm": "configured" if config.GROQ_API_KEY else "missing_key"}
    try:
        agent.dataset_description()
        from database import get_dataset_summary
        get_dataset_summary()
        checks["cricket_db"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["cricket_db"] = f"error: {e}"
    healthy = checks["cricket_db"] == "ok" and checks["llm"] == "configured"
    return {"status": "ok" if healthy else "degraded", "checks": checks, "uptime_s": int(time.time() - STARTED_AT)}


# ── Sessions ─────────────────────────────────────────────────────────────────

@app.get("/sessions")
def list_sessions(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=100),
    identity: Identity = Depends(get_identity),
):
    sessions = get_user_sessions(identity.user_id, identity.anon_ip, limit=limit + 1, offset=offset, search=q)
    return {"sessions": sessions[:limit], "has_more": len(sessions) > limit}


@app.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    identity: Identity = Depends(get_identity),
):
    state = _session_or_404(session_id, identity)
    return {
        "session": {"id": session_id, "title": state["title"], "created_at": state["created_at"],
                    "updated_at": state["updated_at"]},
        "messages": get_recent_messages(session_id, limit=limit),
    }


@app.patch("/sessions/{session_id}")
def rename_session(session_id: str, body: RenameSessionRequest, identity: Identity = Depends(get_identity)):
    _session_or_404(session_id, identity)
    update_session_title(session_id, body.title, identity.user_id, identity.anon_ip)
    return {"id": session_id, "title": get_session_state(session_id)["title"]}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, identity: Identity = Depends(get_identity)):
    _session_or_404(session_id, identity)
    delete_session_db(session_id, identity.user_id, identity.anon_ip)
    memory.invalidate_cache(session_id)
    return {"success": True}


# ── Asking ───────────────────────────────────────────────────────────────────

def prepare_turn(body: QuestionRequest, identity: Identity) -> tuple[str, str]:
    """Validate everything that should fail fast with an HTTP error, before any LLM work."""
    question = " ".join(body.question.split())
    if not question:
        raise HTTPException(status_code=422, detail="Please type a question.")

    session_id = body.session_id or str(uuid.uuid4())
    if not SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=422, detail="Invalid conversation id.")
    if get_session_state(session_id) is not None:
        _session_or_404(session_id, identity)

    quota = current_quota(identity)
    if not quota["allowed"]:
        if identity.user:
            message = (f"You've used your {quota['limit']:,} token allowance for this month. "
                       f"It resets on {quota['reset_date']}.")
        else:
            message = (f"You've used your {quota['limit']} free questions. "
                       "Create a free account to keep going.")
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "message": message, "quota": quota})
    return question, session_id


def _summarizer(identity: Identity, session_id: str):
    def run(old_summary, messages):
        usage = agent.Usage()
        try:
            return agent.summarize(old_summary, messages, usage)
        finally:
            tokens = usage.as_dict()
            if tokens["total"]:
                log_token_usage(identity.user_id, "[conversation summary]", "summarizer", tokens["input"],
                                tokens["output"], ip_address=identity.ip, request_type="summary",
                                session_id=session_id)
    return run


def execute_turn(question: str, session_id: str, identity: Identity, on_event=None) -> dict:
    ctx = memory.load_context(session_id)
    result = agent.ask(question, session_id=session_id, on_event=on_event, context=ctx)
    error = result.get("error")

    saved = save_turn(session_id, question, result, user_id=identity.user_id, anon_ip=identity.anon_ip)
    memory.record_turn(session_id, ctx["ledger"], question, result.get("tool"), result.get("args"),
                       succeeded=error is None)

    tokens = result["tokens"]
    try:
        log_token_usage(
            user_id=identity.user_id, question=question, tool_used=result.get("tool") or "unknown",
            input_tokens=tokens["input"], output_tokens=tokens["output"], success=error is None,
            error_message=f"[{error['code']}] {error.get('detail')}" if error else None,
            latency_ms=result["timings"].get("total_ms"), ip_address=identity.ip,
            request_type="ask", session_id=session_id,
        )
    except Exception as e:  # noqa: BLE001 - accounting must never lose the user's answer
        log.error("Failed to log token usage: %s", e)

    if error is None:
        memory.maybe_summarize(session_id, _summarizer(identity, session_id))

    if error:
        result["error"] = {"code": error["code"], "message": error["message"]}  # hide internals
    result["session_id"] = session_id
    result["message_id"] = saved["assistant_message_id"]
    result["quota"] = current_quota(identity)
    return result


@app.post("/ask")
def ask_question(body: QuestionRequest, identity: Identity = Depends(get_identity)):
    question, session_id = prepare_turn(body, identity)
    return execute_turn(question, session_id, identity)


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/ask/stream")
def ask_question_stream(body: QuestionRequest, identity: Identity = Depends(get_identity)):
    """Server-sent events: `status` events for each pipeline stage, then one `result`."""
    question, session_id = prepare_turn(body, identity)
    events: queue.Queue = queue.Queue()
    done = object()

    def worker():
        try:
            events.put(("result", execute_turn(question, session_id, identity, on_event=lambda e: events.put(("status", e)))))
        except Exception as e:  # noqa: BLE001
            log.exception("Streaming turn failed")
            events.put(("error", {"code": "internal_error", "message": "Something went wrong. Please try again.",
                                  "detail": type(e).__name__}))
        finally:
            events.put(done)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        yield _sse("session", {"session_id": session_id})
        while True:
            try:
                item = events.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is done:
                return
            yield _sse(*item)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
