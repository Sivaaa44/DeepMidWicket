"""
Conversation memory for multi-turn context.

SQLite is the source of truth for everything (messages, entity ledger, rolling
summary). Redis, when available, is a read-through cache of the assembled context
that is invalidated on every write, so the two stores can never disagree.

Context = entity ledger (recently referenced players/teams/places/seasons, most
recent first) + rolling summary of older turns + hot window of the latest turns.
"""
import json
import logging
import re
import threading

import config
from auth_database import (
    get_context_messages, get_session_state, get_unsummarized_messages, save_session_memory,
)
from database import get_known_entities

log = logging.getLogger("memory")

LEDGER_KEYS = ("people", "organizations", "places", "dates", "identifiers")


# ── Redis (optional cache) ───────────────────────────────────────────────────

def _connect_redis():
    if not (config.REDIS_URL or config.REDIS_HOST):
        return None
    try:
        import redis
        if config.REDIS_URL:
            client = redis.Redis.from_url(config.REDIS_URL, decode_responses=True, socket_timeout=1.0)
        else:
            client = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB,
                                 decode_responses=True, socket_timeout=1.0)
        client.ping()
        log.info("Redis connected; using it as the session context cache.")
        return client
    except Exception as e:  # noqa: BLE001 - any failure means "run without cache"
        log.warning("Redis unavailable (%s); context is served from SQLite only.", e)
        return None


redis_client = _connect_redis()


def redis_status() -> str:
    if redis_client is None:
        return "disabled"
    try:
        redis_client.ping()
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


def _cache_key(session_id: str) -> str:
    return f"session:{session_id}:context"


def invalidate_cache(session_id: str):
    if redis_client is None or not session_id:
        return
    try:
        # Also clear keys written by older versions of the app.
        redis_client.delete(
            _cache_key(session_id),
            f"session:{session_id}:ledger",
            f"session:{session_id}:summary",
            f"session:{session_id}:hot_window",
            f"session:{session_id}:pending_summarization",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Redis invalidate failed: %s", e)


# ── Entity extraction ────────────────────────────────────────────────────────

class EntityIndex:
    def __init__(self):
        try:
            self.people, self.organizations, self.places = get_known_entities()
        except Exception as e:  # noqa: BLE001
            log.error("Could not load known entities: %s", e)
            self.people, self.organizations, self.places = set(), set(), set()
        log.info("Entity index: %d people, %d teams, %d places",
                 len(self.people), len(self.organizations), len(self.places))

    @staticmethod
    def _words(text: str):
        words, caps = [], []
        for match in re.finditer(r"\b\w+\b", text):
            word = match.group()
            if word.lower() == "s":  # possessive "Kohli's"
                continue
            words.append(word.lower())
            caps.append(word[0].isupper())
        return words, caps

    def _match(self, text: str, entities, threshold: int) -> list[str]:
        text_lower = text.lower()
        q_words, q_caps = self._words(text)
        q_set = set(q_words)
        candidates = []
        for entity in entities:
            entity_lower = entity.lower()
            tokens = entity_lower.split()
            significant = [t for t in tokens if len(t) > threshold] or [entity_lower]
            if not all(t in q_set for t in significant):
                if not re.search(r"\b" + re.escape(entity_lower) + r"\b", text_lower):
                    continue
                candidates.append((entity, len(significant)))
                continue
            if self._contradicts(tokens, significant, q_words, q_caps):
                continue
            candidates.append((entity, len(significant)))
        if not candidates:
            return []
        best = max(score for _, score in candidates)
        return sorted(e for e, score in candidates if score == best)

    @staticmethod
    def _contradicts(tokens, significant, q_words, q_caps) -> bool:
        """A capitalised neighbouring word that disagrees with the entity's initials/names."""
        for t in significant:
            if t not in tokens:
                continue
            e_idx = tokens.index(t)
            for q_idx, qw in enumerate(q_words):
                if qw != t:
                    continue
                for other_idx, other in enumerate(tokens):
                    if other_idx == e_idx:
                        continue
                    target = q_idx + other_idx - e_idx
                    if 0 <= target < len(q_words) and q_caps[target]:
                        word = q_words[target]
                        if (len(other) == 1 and not word.startswith(other)) or (len(other) > 1 and word != other):
                            return True
        return False

    def extract(self, text: str) -> dict:
        if not text:
            return {k: [] for k in LEDGER_KEYS}
        dates = re.findall(r"\b(20[0-3]\d(?:/\d{2})?)\b", text) + re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
        ids = [i for i in re.findall(r"\b(\d{5,7})\b", text) if i not in dates]
        return {
            "people": self._match(text, self.people, 2),
            "organizations": self._match(text, self.organizations, 3),
            "places": self._match(text, self.places, 4),
            "dates": list(dict.fromkeys(dates)),
            "identifiers": list(dict.fromkeys(ids)),
        }


_entity_index = None
_entity_lock = threading.Lock()


def entity_index() -> EntityIndex:
    global _entity_index
    if _entity_index is None:
        with _entity_lock:
            if _entity_index is None:
                _entity_index = EntityIndex()
    return _entity_index


def empty_ledger() -> dict:
    return {k: [] for k in LEDGER_KEYS}


def normalize_ledger(raw) -> dict:
    ledger = empty_ledger()
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    if isinstance(raw, dict):
        for k in LEDGER_KEYS:
            values = raw.get(k) or []
            if isinstance(values, list):
                ledger[k] = [str(v) for v in values if v]
    return ledger


def merge_ledger(old: dict, mentioned: dict) -> dict:
    """
    Recency-ordered merge: newly mentioned entities move to the front (most recent
    first), duplicates collapse, and each category keeps the N most recent.
    """
    merged = {}
    for key in LEDGER_KEYS:
        fresh = [v for v in mentioned.get(key, []) if v]
        combined = list(dict.fromkeys(fresh + [v for v in old.get(key, []) if v not in fresh]))
        merged[key] = combined[:config.LEDGER_MAX_PER_CATEGORY]
    return merged


def entities_from_turn(question: str, tool: str, args: dict, known_people=()) -> dict:
    """Entities from the question plus the router's resolved arguments (which already
    have pronouns like "his" replaced by the actual player)."""
    index = entity_index()
    found = index.extract(question)
    resolved_text = []
    args = args or {}
    for key in ("player_name", "player1", "player2"):
        if args.get(key):
            resolved_text.append(str(args[key]))
    if tool == "general_query" and args.get("question"):
        resolved_text.append(str(args["question"]))
    if args.get("season"):
        found["dates"] = [str(args["season"])] + found["dates"]
    for text in resolved_text:
        extra = index.extract(text)
        if len(extra["people"]) > 1 and len(text.split()) <= 3:
            extra["people"] = []  # ambiguous surname ("Sharma"): keep the raw name instead
        for key in LEDGER_KEYS:
            found[key] = list(dict.fromkeys(extra[key] + found[key]))
    # A bare keyword like "Kohli" resolves to someone already in the conversation if possible;
    # otherwise the raw name is still worth keeping.
    for key in ("player_name", "player1", "player2"):
        name = str(args.get(key) or "")
        if not name or any(name.lower() in p.lower() for p in found["people"]):
            continue
        prior = next((p for p in known_people if name.lower() in p.lower()), None)
        found["people"].insert(0, prior or name)
    return found


# ── Context assembly ─────────────────────────────────────────────────────────

def load_context(session_id: str) -> dict:
    """Return {ledger, summary, hot_window} for a session (empty for a new one)."""
    if not session_id:
        return {"ledger": empty_ledger(), "summary": "", "hot_window": []}

    if redis_client is not None:
        try:
            cached = redis_client.get(_cache_key(session_id))
            if cached:
                ctx = json.loads(cached)
                ctx["ledger"] = normalize_ledger(ctx.get("ledger"))
                return ctx
        except Exception as e:  # noqa: BLE001
            log.warning("Redis read failed: %s", e)

    state = get_session_state(session_id) or {}
    ctx = {
        "ledger": normalize_ledger(state.get("ledger")),
        "summary": state.get("summary") or "",
        "hot_window": get_context_messages(session_id, config.HOT_WINDOW_MESSAGES),
    }

    if redis_client is not None and state:
        try:
            redis_client.set(_cache_key(session_id), json.dumps(ctx), ex=config.SESSION_CACHE_TTL_SECONDS)
        except Exception as e:  # noqa: BLE001
            log.warning("Redis write failed: %s", e)
    return ctx


def format_context(ctx: dict) -> str:
    parts = []
    ledger = ctx.get("ledger") or {}
    lines = [f"- {k.capitalize()} (most recent first): {', '.join(v)}" for k, v in ledger.items() if v]
    if lines:
        parts.append("=== ENTITIES REFERENCED IN THIS CONVERSATION ===\n" + "\n".join(lines))
    if ctx.get("summary"):
        parts.append("=== EARLIER CONVERSATION SUMMARY ===\n" + ctx["summary"])
    if ctx.get("hot_window"):
        dialogue = []
        for m in ctx["hot_window"]:
            role = "User" if m["role"] == "user" else "Assistant"
            dialogue.append(f"{role}: {m['content']}")
        parts.append("=== RECENT DIALOGUE (oldest to newest) ===\n" + "\n".join(dialogue))
    return "\n\n".join(parts)


def record_turn(session_id: str, ledger: dict, question: str, tool: str, args: dict, succeeded: bool) -> dict:
    """Update the entity ledger after a persisted turn and drop the cached context."""
    new_ledger = ledger
    if succeeded:
        new_ledger = merge_ledger(ledger, entities_from_turn(question, tool, args, ledger.get("people", [])))
        save_session_memory(session_id, ledger=new_ledger)
    invalidate_cache(session_id)
    return new_ledger


# ── Rolling summary ──────────────────────────────────────────────────────────

_summarizing: set[str] = set()
_summarizing_lock = threading.Lock()


def pending_summary_messages(session_id: str) -> list[dict]:
    """Messages that have aged out of the hot window and are not yet summarised."""
    hot = get_context_messages(session_id, config.HOT_WINDOW_MESSAGES)
    if not hot:
        return []
    return get_unsummarized_messages(session_id, before_id=hot[0]["id"])


def maybe_summarize(session_id: str, summarize_fn):
    """
    Fold aged-out messages into the rolling summary in a background thread once a
    batch has accumulated. `summarize_fn(old_summary, messages) -> str`.
    Works identically with or without Redis.
    """
    if not session_id:
        return
    pending = pending_summary_messages(session_id)
    if len(pending) < config.SUMMARIZE_BATCH_MESSAGES:
        return
    with _summarizing_lock:
        if session_id in _summarizing:
            return
        _summarizing.add(session_id)

    def run():
        try:
            state = get_session_state(session_id) or {}
            new_summary = summarize_fn(state.get("summary") or "", pending)
            if new_summary:
                save_session_memory(session_id, summary=new_summary, summarized_upto=pending[-1]["id"])
                invalidate_cache(session_id)
                log.info("Summarised %d messages for session %s", len(pending), session_id)
        except Exception as e:  # noqa: BLE001
            log.error("Summarisation failed for %s: %s", session_id, e)
        finally:
            with _summarizing_lock:
                _summarizing.discard(session_id)

    threading.Thread(target=run, daemon=True).start()
