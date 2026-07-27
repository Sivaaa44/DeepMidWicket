# Fix: Table data disappearing on chat reload

## Problem
When reloading a session or switching back to an old chat, only the question and the text answer come back — the data table (which has most of the actual info) is gone. Right now it looks like we're only persisting the text response, not the structured query result that generated the table.

## What we want
Don't re-run the SQL query when a session loads. Instead, snapshot the result at the time it was first generated and just store that alongside the message, so reloading a chat is purely "read from DB and render" — no query execution involved.

Rough idea for the storage side — feel free to adjust naming/structure to whatever fits our existing message schema better:

```sql
CREATE TABLE IF NOT EXISTS message_artifacts (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    sql_query TEXT,
    result_columns TEXT,   -- JSON array of column names
    result_rows TEXT,      -- JSON array of row data
    row_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Store `result_columns` and `result_rows` as JSON so the frontend table component can render them the same way regardless of whether the data is fresh from a live query or pulled from history — one render path, not two.

Keep the `sql_query` text too, even though we're not auto-re-running it — useful later for a "show query" toggle, and leaves the door open for an optional manual "re-run" button if we ever want one.

## Behavior on load
- Loading an old session should pull the stored `result_columns` + `result_rows` and render the table directly. No DB query execution on session load, period.
- If a message never had a table (pure text answer), this artifact just won't exist for that message — that's fine, don't force an empty row.

## Things to keep in mind
- Cap how many rows we store per artifact (100–200ish) — this is for display continuity, not meant to be a full data export.
- Historical tables should stay frozen as "what was shown at the time," not silently update if the underlying data changes later. Don't build in any automatic refresh-on-load behavior.
- Make sure this hooks into wherever we currently save messages/session context, so it's one atomic save per turn (message + artifact together), not two separate calls that could get out of sync.

Go ahead and figure out the cleanest way to wire this into the existing save/load flow — just flag it if the current message schema makes storing this awkward and we might need to restructure something first.