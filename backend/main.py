from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import ask

app = FastAPI(title="Cricket Intelligence Agent")

# Allow React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {"status": "Cricket Intelligence Agent is running"}


@app.post("/ask")
def ask_question(request: QuestionRequest):
    result = ask(request.question)
    return result