import os

from dotenv import load_dotenv
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask
from auth_routes import router as auth_router
from auth import decode_token, oauth2_scheme
from auth_database import log_token_usage

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


@app.get("/")
def root():
    return {"status": "Cricket Intelligence Agent is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask_question(request: QuestionRequest, token: str = Depends(oauth2_scheme)):
    result = ask(request.question)

    if token:
        try:
            user = decode_token(token)
            user_id = user["id"]
            question = request.question
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