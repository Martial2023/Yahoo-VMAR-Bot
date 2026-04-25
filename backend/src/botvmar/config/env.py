"""Static configuration loaded from .env (secrets and infra only).

Tunable bot parameters (mode, quotas, prompt, ticker, alert emails…) are stored
in Postgres and accessed via `botvmar.config.runtime`.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# env.py is at backend/src/botvmar/config/env.py
#   parents[0]=config  parents[1]=botvmar  parents[2]=src  parents[3]=backend
_pkg_root = Path(__file__).resolve().parents[3]
_env_path = _pkg_root / ".env"
load_dotenv(_env_path)

# --- Database ---
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# --- API control ---
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
API_TOKEN: str = os.getenv("API_TOKEN", "")

# --- Secrets (jamais en BDD) ---
OPENROUTER_KEY: str = os.getenv("OPENROUTER_KEY", "")
YAHOO_EMAIL: str = os.getenv("YAHOO_EMAIL", "")
YAHOO_PASSWORD: str = os.getenv("YAHOO_PASSWORD", "")
PROXY_URL: str = os.getenv("PROXY_URL", "")

# --- SMTP (alertes email) ---
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM: str = os.getenv("SMTP_FROM", "")

# --- Telegram (alertes optionnelles) ---
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Logging ---
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# --- Paths (toutes relatives au dossier backend/) ---
PROJECT_ROOT: Path = _pkg_root
DATA_DIR: Path = PROJECT_ROOT / "data"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
SCREENSHOTS_DIR: Path = LOGS_DIR / "screenshots"
SESSIONS_DIR: Path = PROJECT_ROOT / "sessions"
SESSION_FILE: str = os.getenv("SESSION_FILE", "sessions/yahoo_session.json")

for _d in (DATA_DIR, LOGS_DIR, SCREENSHOTS_DIR, SESSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
