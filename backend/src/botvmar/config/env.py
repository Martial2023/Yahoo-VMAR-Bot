"""Static configuration loaded from .env (secrets and infra only).

Tunable bot parameters (mode, quotas, prompt, ticker, alert emails…) are stored
in Postgres and accessed via `botvmar.config.runtime`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


_pkg_root = Path(__file__).resolve().parents[3]
_env_path = _pkg_root / ".env"
load_dotenv(_env_path)


DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# --- API control ---
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_TOKEN: str = os.getenv("API_TOKEN", "")


OPENROUTER_KEY: str = os.getenv("OPENROUTER_KEY", "")
YAHOO_EMAIL: str = os.getenv("YAHOO_EMAIL", "")
YAHOO_PASSWORD: str = os.getenv("YAHOO_PASSWORD", "")
PROXY_URL: str = os.getenv("PROXY_URL", "")

# --- Reddit (script-type app — https://www.reddit.com/prefs/apps) ---
REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME: str = os.getenv("REDDIT_USERNAME", "")
REDDIT_PASSWORD: str = os.getenv("REDDIT_PASSWORD", "")
REDDIT_USER_AGENT: str = os.getenv(
    "REDDIT_USER_AGENT",
    "BotVMAR/0.1 (by /u/unknown)",
)


SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "")


TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# Run a full cycle for all enabled platforms as soon as the worker starts.
RUN_ON_STARTUP: bool = os.getenv("RUN_ON_STARTUP", "true").strip().lower() in ("1", "true", "yes")


PROJECT_ROOT: Path = _pkg_root
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
SCREENSHOTS_DIR: Path = LOGS_DIR / "screenshots"
SESSIONS_DIR: Path = PROJECT_ROOT / "sessions"
SESSION_FILE: str = os.getenv("SESSION_FILE", "sessions/yahoo_session.json")

for _d in (DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, SESSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
