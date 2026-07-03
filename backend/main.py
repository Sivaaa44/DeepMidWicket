import os
import time
import uuid
from typing import Optional

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask
from auth_routes import router as auth_router
from admin_routes import router as admin_router
from auth import decode_token, oauth2_scheme
from auth_database import log_token_usage, check_user_limit, save_message

load_dotenv()

app = FastAPI(title="Cricket Intelligence Agent")

# Include Auth Routerx` `
app.include_router(auth_router, prefix="/auth")

# Include Admin Router
app.include_router(admin_router, prefix="/admin")

_allowed = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
origins = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


# In-memory store for anonymous IP usage
anonymous_ip_usage = {}


@app.get("/")
def root():
    return {"status": "Cricket Intelligence Agent is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_question(
    question_request: QuestionRequest, 
    request: Request, 
    background_tasks: BackgroundTasks,
    token: str = Depends(oauth2_scheme)
):
    user_id = None
    user = None
    client_ip = request.client.host if request.client else "unknown"

    if token:
        try:
            user = decode_token(token)
            user_id = user["id"]
        except Exception:
            pass

    if user_id:
        # Check token limit for authenticated user
        limit_info = check_user_limit(user_id)
        if not limit_info["allowed"]:
            raise HTTPException(
                status_code=429,
                detail="Monthly limit reached (50,000 tokens). Usage resets on the 1st."
            )
    else:
        # Anonymous user: track by IP
        current_count = anonymous_ip_usage.get(client_ip, 0)
        if current_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Sign up for free to ask more questions."
            )
        anonymous_ip_usage[client_ip] = current_count + 1

    # Extract or generate session_id
    session_id = question_request.session_id or str(uuid.uuid4())

    start_time = time.perf_counter()
    success = 1
    error_message = None
    result = None

    try:
        # Execute ask with session context parameters
        result = ask(question_request.question, session_id=session_id, user_id=user_id)
        if result and (result.get("data") is None or "Error:" in str(result.get("answer", "")) or "An internal error occurred" in str(result.get("answer", ""))):
            success = 0
            error_message = result.get("answer") or "Unknown agent error"
    except Exception as e:
        success = 0
        error_message = str(e)
        result = {
            "question": question_request.question,
            "tool": "unknown",
            "args": {},
            "sql": None,
            "answer": "An internal error occurred. Please try again later.",
            "data": None,
            "tokens": {"input": 0, "output": 0, "total": 0}
        }

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    # Queue async write-through to SQLite
    background_tasks.add_task(save_message, session_id, "user", question_request.question)
    background_tasks.add_task(save_message, session_id, "assistant", result.get("answer", ""))

    # Inject session_id into response
    result["session_id"] = session_id

    # Log token usage (for both authenticated and anonymous requests)
    try:
        tokens = result.get("tokens") or {"input": 0, "output": 0, "total": 0}
        input_tokens = tokens.get("input", 0)
        output_tokens = tokens.get("output", 0)
        tool_used = result.get("tool") or "unknown"

        log_token_usage(
            user_id=user_id,
            question=question_request.question,
            tool_used=tool_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            success=success,
            error_message=error_message,
            latency_ms=latency_ms,
            ip_address=client_ip
        )
    except Exception as log_err:
        print(f"Failed to log token usage: {log_err}")

    return result