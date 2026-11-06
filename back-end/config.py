"""Settings read from the environment (the root `.env` file or real env vars).

Keep every tunable value here so there is one place to look and one place to
document (see `.env.example`).
"""

import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())


def env_flag(name: str, default: bool = False) -> bool:
    """True for 1/true/yes/on (any case), False for anything else; `default` when unset."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# Address of the web app: allowed by CORS and used in links sent over WhatsApp
FRONT_URL = os.getenv("FRONT_URL", "http://localhost:5173").rstrip("/")

# Model used by every agent
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Where the built web app is, when this server also serves it (the production image sets it; empty in development)
STATIC_DIR = os.getenv("STATIC_DIR", "").strip()

# Database connections kept per process. The defaults suit development; a deployment on a shared database server sets
# them small (see docs/DEPLOY.md)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# Print every SQL statement to the log (noisy; for debugging only)
SQL_ECHO = env_flag("SQL_ECHO")
