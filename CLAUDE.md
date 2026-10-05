# DeepMidWicket — Cricket Intelligence

Natural-language IPL analytics: a question is routed to a tool, turned into SQLite over
ball-by-ball data, executed read-only, and answered with an analyst-style summary plus a
chart/table. FastAPI + Groq backend, React 19 + Vite + Tailwind v4 frontend.

## Commands

```bash
# Backend (run from backend/ — modules import each other flatly)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload                 # http://127.0.0.1:8000
python -m unittest -v                     # tests; LLM is mocked, users DB is a temp file

# Frontend
cd frontend
npm install
npm run dev                               # http://localhost:5173, API from VITE_API_URL
npm run build                             # must pass before pushing
```

Config lives in `backend/.env` (template: `backend/.env.example`). Minimum: `GROQ_API_KEY`.
Set `ADMIN_EMAILS` to reach `/admin`, and `JWT_SECRET` to stay signed in across restarts.

## Layout

```
backend/
  config.py        every env var and tunable — read config.X at call time, never hardcode
  main.py          HTTP glue: /ask, /ask/stream (SSE), /sessions*, /health
  agent.py         pipeline: route → build SQL prompt → generate SQL → run (1 repair) → answer
  memory.py        conversation context: entity ledger + rolling summary + hot window
  database.py      cricket.db: read-only, time-limited query runner, schema prompt, indexes
  auth.py          JWT, bcrypt, Identity (user or anonymous IP), require_admin
  auth_database.py users.db: users, token_usage, sessions, messages, message_artifacts
  admin_routes.py  /admin/* monitoring API
  test_api.py      end-to-end tests with FakeLLM
frontend/src/
  App.jsx          auth/guest gate, routing (/ and /admin), chat shell
  lib/api.js       the only HTTP client (fetch + SSE parsing, ApiError)
  lib/useChat.js   active conversation state; lib/useSessions.js sidebar list
  lib/viz.js       picks chart form from result shape; lib/format.js formatting helpers
  components/answer/   Answer.jsx dispatches to chart/comparison/head-to-head/tiles/table/SQL
  components/admin/    admin dashboard tabs
data_loader.py     rebuilds cricket.db from ./ipl_json (not needed at runtime)
```

## Architecture rules

- **SQLite is the source of truth for conversation memory.** Redis is only an optional
  read-through cache of the assembled context, invalidated on every write
  (`memory.invalidate_cache`). Never write state to Redis that isn't also in SQLite.
- **A turn is saved atomically** via `auth_database.save_turn` (question + answer + result
  snapshot in one transaction), synchronously before the response returns. Failed turns are
  stored with `is_error=1` and excluded from model context by `get_context_messages`.
- **`agent.ask` never raises.** Failures come back as `result["error"] = {code, message}`;
  raise `AgentError(code, user_message, detail)` inside the pipeline. `detail` is logged
  and stored in `token_usage.error_message`; `main.py` strips it before responding.
- **All LLM calls go through `agent.llm_call`** — it maps Groq errors, records token usage
  (even on failure), handles reasoning models (`openai/gpt-oss-*` get `reasoning_effort`
  and hidden reasoning) and turns `finish_reason == "length"` into `llm_truncated`.
  Reasoning models spend output tokens thinking: keep `MAX_TOKENS_*` generous.
- **Generated SQL is untrusted.** `database.run_query` opens cricket.db read-only, allows a
  single SELECT/WITH statement and enforces `SQL_TIMEOUT_SECONDS`. Don't loosen this.
- **The router resolves follow-ups.** `general_query` receives a self-contained rewritten
  question in `args["question"]`; player tools receive resolved names. SQL prompts get no
  chat history — fix context problems in the router prompt or the ledger, not there.
- **Every session endpoint checks ownership** with `can_access_session` and returns 404
  (not 403) for other people's sessions. `/ask` checks it too.
- **Quotas:** signed-in users have a monthly token budget (`users.monthly_token_limit`,
  default `DEFAULT_MONTHLY_TOKEN_LIMIT`); guests get `ANON_QUERY_LIMIT` questions per
  `ANON_WINDOW_HOURS`, counted from `token_usage` by IP. Usage rows use
  `request_type` (`ask` | `summary`); admin stats count questions with `request_type='ask'`.
- Schema changes to users.db go in `auth_database.init_db` as idempotent `_add_column`
  migrations — existing databases must keep working.

## Frontend conventions

- One render path: live answers and answers restored from history have the same shape
  and both go through `components/answer/Answer.jsx`.
- Use the design tokens in `src/index.css` (`text-ink-1/2/3`, `border-line`, `bg-hover`,
  `glass`, `var(--series-N)`, status colors). No hardcoded hex for UI or chart colors.
- Charts: one series per chart (switch metrics with chips, never two y-axes); categorical
  colors in fixed order `--series-1..4` (validated CVD-safe on the dark surface); status
  colors only for good/bad states and always with an icon + label.
- Network calls only via `lib/api.js`; surface failures with `toast` or an inline error,
  never `console.error` alone.
- The app is dark-only by design.

## Testing

- `test_api.py` sets `USERS_DB_PATH` to a temp file **before** importing app modules and
  patches `agent.llm_call` with `FakeLLM`. Follow that pattern; tests must never call Groq
  or touch the real `users.db`.
- Add a test for any change to auth, ownership, quotas, memory or the agent pipeline.

## Don'ts

- Never commit `backend/users.db` (or backups of it) or any `.env` file — they hold user
  emails, password hashes and API keys.
- Don't modify `backend/cricket.db` casually: it's tracked and already indexed. If you rebuild
  it with `data_loader.py`, `database.ensure_indexes()` recreates the indexes on startup.
- Don't add a second HTTP client, state library or chart library without a strong reason.
