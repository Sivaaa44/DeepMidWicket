# DeepMidWicket

Ask questions about the IPL in plain English and get analyst-style answers backed by
ball-by-ball data, with charts, tables and the SQL that produced them.

> *"How has Virat Kohli fared against Jasprit Bumrah?"* · *"Best economy in IPL finals?"* ·
> *"Compare Rohit Sharma and David Warner in the powerplay"*

## How it works

1. **Route.** An LLM classifies the question (player stats, two-player comparison or
   head-to-head, general query, or chat) and resolves follow-ups like *"his death-overs
   strike rate"* using the conversation's context.
2. **Query.** It writes SQLite for the question, which runs read-only and time-limited
   against 1,235 matches and ~294k deliveries (2008–2026). A failed query is repaired once.
3. **Answer.** The results become a short written analysis, and the UI picks a chart for
   the data's shape: rankings, season trends, side-by-side comparisons or matchup breakdowns.

Conversations keep a ledger of entities mentioned recently, a rolling summary and a window
of recent turns, so multi-turn questions stay coherent.

## Features

- Streaming progress through each pipeline stage
- Chat history with search, rename and delete; results are saved and restored exactly as shown
- Accounts with monthly token budgets, plus a limited guest mode
- Admin dashboard: usage, latency, errors, tool mix, user management and an activity log
- Every answer exposes its SQL and data, with CSV export

## Stack

| Layer    | Tech |
|----------|------|
| Backend  | Python, FastAPI, Groq (Llama / gpt-oss), SQLite, optional Redis |
| Frontend | React 19, Vite, Tailwind CSS v4, Recharts |
| Deploy   | Render (API), Vercel (web) |

## Getting started

**Prerequisites:** Python 3.11+, Node 20+, a [Groq API key](https://console.groq.com/keys).

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                               # set GROQ_API_KEY (and ADMIN_EMAILS for /admin)
uvicorn main:app --reload                          # http://127.0.0.1:8000

# Frontend (new terminal)
cd frontend
npm install
cp .env.example .env.local                         # VITE_API_URL=http://localhost:8000
npm run dev                                        # http://localhost:5173
```

`backend/cricket.db` ships with the repo, already indexed. To rebuild it from Cricsheet IPL
JSON, set `JSON_FOLDER` and `DB_PATH` at the top of `data_loader.py` and run it.

## Configuration

All settings are environment variables, documented in
[`backend/.env.example`](backend/.env.example). The main ones:

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Required. LLM access |
| `LLM_MODEL` | Model used for routing, SQL and answers |
| `JWT_SECRET` | Login token signing key (required in production) |
| `ADMIN_EMAILS` | Accounts that can open `/admin` |
| `DEFAULT_MONTHLY_TOKEN_LIMIT` / `ANON_QUERY_LIMIT` | Usage quotas |
| `REDIS_URL` | Optional context cache; SQLite is always the source of truth |

## Project structure

```
backend/    FastAPI app — agent pipeline, memory, auth, admin API, tests
frontend/   React app — chat UI, result visualizations, admin dashboard
data_loader.py   Builds cricket.db from raw match JSON
DEPLOY.md        Render + Vercel deployment guide
```

## Testing

```bash
cd backend && python -m unittest -v    # LLM is mocked; uses a temporary users database
cd frontend && npm run build
```

## Deployment

See [DEPLOY.md](DEPLOY.md). In production, set `ENVIRONMENT=production` and `JWT_SECRET`,
and give `users.db` a persistent disk via `USERS_DB_PATH`.
