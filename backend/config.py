"""Central configuration. Every tunable lives here and is read from the environment."""
import logging
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("config")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("Invalid integer for %s=%r, using default %s", name, raw, default)
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("Invalid float for %s=%r, using default %s", name, raw, default)
        return default


def _list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# ── Storage ──────────────────────────────────────────────────────────────────
CRICKET_DB_PATH = os.getenv("CRICKET_DB_PATH", os.path.join(BASE_DIR, "cricket.db"))
USERS_DB_PATH = os.getenv("USERS_DB_PATH", os.path.join(BASE_DIR, "users.db"))
LOG_DIR = os.getenv("LOG_DIR", os.path.join(BASE_DIR, "logs"))

REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = _int("REDIS_PORT", 6379)
REDIS_DB = _int("REDIS_DB", 0)

# ── LLM ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", LLM_MODEL)  # used for summaries
LLM_TIMEOUT_SECONDS = _float("LLM_TIMEOUT_SECONDS", 30.0)
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 2)
SQL_REPAIR_ATTEMPTS = _int("SQL_REPAIR_ATTEMPTS", 1)

# ── Query execution ──────────────────────────────────────────────────────────
SQL_MAX_ROWS = _int("SQL_MAX_ROWS", 100)
SQL_TIMEOUT_SECONDS = _float("SQL_TIMEOUT_SECONDS", 5.0)
ARTIFACT_MAX_ROWS = _int("ARTIFACT_MAX_ROWS", 100)
MAX_QUESTION_LENGTH = _int("MAX_QUESTION_LENGTH", 1000)

# ── Conversation memory ──────────────────────────────────────────────────────
HOT_WINDOW_MESSAGES = _int("HOT_WINDOW_MESSAGES", 10)  # 5 user/assistant turns
SUMMARIZE_BATCH_MESSAGES = _int("SUMMARIZE_BATCH_MESSAGES", 6)
LEDGER_MAX_PER_CATEGORY = _int("LEDGER_MAX_PER_CATEGORY", 5)
SESSION_CACHE_TTL_SECONDS = _int("SESSION_CACHE_TTL_SECONDS", 7200)
SESSION_TITLE_MAX_LENGTH = _int("SESSION_TITLE_MAX_LENGTH", 80)

# ── Auth & quotas ────────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = _int("JWT_EXPIRE_DAYS", 7)

if not JWT_SECRET:
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET must be set when ENVIRONMENT=production")
    # Ephemeral secret: tokens are invalidated on restart, but nothing guessable ships.
    JWT_SECRET = secrets.token_urlsafe(48)
    log.warning("JWT_SECRET not set; using an ephemeral secret (sessions reset on restart).")

# Optional break-glass key for scripts. Admin UI users authenticate with their JWT.
ADMIN_KEY = os.getenv("ADMIN_KEY", "")
ADMIN_EMAILS = {e.lower() for e in _list("ADMIN_EMAILS")}

DEFAULT_MONTHLY_TOKEN_LIMIT = _int("DEFAULT_MONTHLY_TOKEN_LIMIT", 50_000)
ANON_QUERY_LIMIT = _int("ANON_QUERY_LIMIT", 5)
ANON_WINDOW_HOURS = _int("ANON_WINDOW_HOURS", 24)

# ── HTTP ─────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = _list("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
