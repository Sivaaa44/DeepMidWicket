import os

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask
from auth_routes import router as auth_router
from auth import decode_token, oauth2_scheme
from auth_database import log_token_usage, check_user_limit

load_dotenv()

app = FastAPI(title="Cricket Intelligence Agent")

# Include Auth Router
app.include_router(auth_router, prefix="/auth")

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


# In-memory store for anonymous IP usage
anonymous_ip_usage = {}


@app.get("/")
def root():
    return {"status": "Cricket Intelligence Agent is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_question(question_request: QuestionRequest, request: Request, token: str = Depends(oauth2_scheme)):
    user_id = None
    user = None

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
        client_ip = request.client.host if request.client else "unknown"
        current_count = anonymous_ip_usage.get(client_ip, 0)
        if current_count >= 5:
            raise HTTPException(
                status_code=429,
                detail="Sign up for free to ask more questions."
            )
        anonymous_ip_usage[client_ip] = current_count + 1

    # Execute ask
    result = ask(question_request.question)

    # If authenticated, log the tokens used
    if user_id:
        try:
            question = question_request.question
            tool_used = result.get("tool") or "unknown"
            answer = result.get("answer") or ""

            input_tokens = int(len(question) * 1.3)
            output_tokens = int(len(answer) * 1.3)

            log_token_usage(
                user_id=user_id,
                question=question,
                tool_used=tool_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
        except Exception:
            pass

    return result