import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask

load_dotenv()

app = FastAPI(title="Cricket Intelligence Agent")

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
def ask_question(request: QuestionRequest):
    result = ask(request.question)
    return result