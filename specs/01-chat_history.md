# Feature Spec: Chat History Sidebar

## Goal
Add a ChatGPT/Claude-style history sidebar. User can see a list of their past chat sessions, click one to load its full context back into the main window, and start a new chat that gets saved as a new session.

## Current State (assume already true — verify before building)
- `session_id` is generated per chat and persisted in `localStorage`.
- Session context (hot memory sliding window, rolling summary, entity ledger) is stored in Redis/Valkey, keyed by `session_id`.
- Messages are saved to SQLite via a `save_message` call.
- Browser rehydrates the *active* session on page refresh, but there is no way to browse or switch to a *different* past session.

This spec only covers what's missing: **listing sessions, switching between them, and basic session management (rename/delete).**

---

## 1. Data Model Changes (SQLite)

Add a `sessions` table if it doesn't already exist as a first-class entity (it may currently just be an implicit key in Redis/message rows):

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,              -- same as session_id used in Redis
    user_id TEXT,                     -- nullable, for anonymous/IP-rate-limited users
    anon_ip TEXT,                     -- nullable, fallback identity for anon users
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_preview TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
```

Ensure the existing `messages` table has a `session_id` foreign key and an index on it (`idx_messages_session`) — needed for fast history loads.

**Ownership rule:** a session belongs to `user_id` if logged in, else scoped to `anon_ip` (matches existing anonymous IP-based rate limiting). Sidebar should only ever list sessions owned by the current identity.

---

## 2. Backend API Endpoints (FastAPI)

### `GET /api/sessions`
List sessions for the current user/anon identity, most recent first.
- Query params: `limit` (default 20), `offset` (for pagination / infinite scroll)
- Response: `[{ id, title, updated_at, last_message_preview }]`

### `GET /api/sessions/{session_id}/messages`
Load full message history for a session (to repopulate the chat window on click).
- Must verify the requesting user/IP owns this session → `403` if not.
- Response: `[{ role, content, created_at }]` in chronological order.
- Also re-hydrate Redis session context (hot memory, entity ledger) from this data if it's not already warm in Redis, or trigger a rebuild-from-SQLite path if Redis TTL expired.

### `PATCH /api/sessions/{session_id}`
Rename a session.
- Body: `{ title: string }`

### `DELETE /api/sessions/{session_id}`
Delete a session and cascade-delete its messages + Redis context key.

### Title generation
On the **first** user message of a new session, auto-generate a title:
- Cheapest option: truncate first ~40 chars of the first user message.
- Better option: one cheap LLM call (small/fast model) to summarize the first exchange into a 3-6 word title, written back via an internal update (not blocking the chat response — fire-and-forget after the main response streams).

Update `sessions.title`, `updated_at`, and `last_message_preview` every time a new message is saved (extend the existing `save_message` function to also touch this row).

---

## 3. Frontend Changes (React/Vite)

### New: `<SessionSidebar />` component
- On mount, `GET /api/sessions` and render list (title + relative timestamp, e.g. "2h ago").
- Highlight the currently active session.
- Click a session → 
  1. Set `session_id` in state + `localStorage` to the clicked session's id.
  2. `GET /api/sessions/{id}/messages`, replace the chat window's message list with the response.
  3. Do **not** create a new backend session — just point the existing chat UI at this `session_id` for subsequent messages.
- "New Chat" button → generate a fresh `session_id` client-side (or request one from backend), clear the message window, don't add to sidebar list until the first message is actually sent (avoids empty-session clutter).
- Optional: hover menu per session for Rename / Delete (calls the PATCH/DELETE endpoints above).

### State management
- Lift `session_id` to whatever top-level state/context already manages chat (you already have this for Phase 1's "new chat" button — extend it, don't duplicate it).
- Sidebar list should optimistically re-order/update `updated_at` and `last_message_preview` when a message is sent in the active session, rather than re-fetching the whole list every time.

---

## 4. Edge Cases to Handle
- Deleting the currently active session → clear chat window and behave like "New Chat".
- Empty state → sidebar shows "No conversations yet" instead of a blank list.
- Pagination — don't load all sessions at once if a user has hundreds; use `limit`/`offset` with a "Load more" or infinite scroll.
- Session ownership check on every session-scoped endpoint — a user must never be able to load another user's session by guessing/incrementing an ID. Since IDs are likely UUIDs already this is low-risk but still verify ownership server-side, not just via unguessable ID.
- Redis TTL expiry — if a session's hot-memory context expired in Redis but the session still exists in SQLite, loading it should rebuild a fresh context (or gracefully degrade to "loaded from history, context will rebuild on next message") rather than erroring.

---

## 5. Suggested Build Order
1. `sessions` table + migration.
2. Extend `save_message` to upsert `sessions` row (title/preview/updated_at) — do this before any UI work so data starts accumulating.
3. `GET /api/sessions` + `GET /api/sessions/{id}/messages` endpoints.
4. Sidebar UI: list + click-to-load (no rename/delete yet).
5. Title auto-generation (start with truncation, upgrade to LLM summary later).
6. Rename/Delete endpoints + UI.
7. Pagination once list-loading works end-to-end.

---

## 6. Testing Checklist
- [ ] New chat → send message → session appears in sidebar with generated title.
- [ ] Click old session → messages load correctly, context continues coherently on next message.
- [ ] Refresh page mid-session → still on the same session (existing Phase 1 behavior, shouldn't regress).
- [ ] Delete active session → falls back to new-chat state cleanly.
- [ ] Two different anon IPs (or two users) never see each other's sessions.
- [ ] Sidebar performs fine with 50+ sessions (pagination/scroll works).