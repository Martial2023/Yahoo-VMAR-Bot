"""Shared auto-login dispatcher used by adapters when a session expires."""

from __future__ import annotations

from botvmar.auth.imap_reader import ImapConfig
from botvmar.auth.login_reddit import auto_login_reddit
from botvmar.auth.login_stocktwits import auto_login_stocktwits
from botvmar.auth.login_yahoo import auto_login_yahoo
from botvmar.db.repositories.settings import get_settings
from botvmar.utils.logger import get_logger

logger = get_logger("auth.auto_login")

_LOGIN_FNS = {
    "yahoo_finance": auto_login_yahoo,
    "stocktwits": auto_login_stocktwits,
    "reddit": auto_login_reddit,
}


async def attempt_auto_login(platform: str, credentials: dict) -> bool:
    """Try to auto-login for *platform* using *credentials* + global IMAP config.

    Returns True on success.
    """
    login_fn = _LOGIN_FNS.get(platform)
    if login_fn is None:
        logger.warning("No auto-login implementation for platform '%s'", platform)
        return False

    if not credentials:
        logger.warning("[%s] no credentials configured — cannot auto-login", platform)
        return False

    # Load global IMAP config from bot_settings
    try:
        settings = await get_settings()
    except Exception as e:
        logger.error("Failed to load bot_settings for IMAP config: %s", e)
        return False

    imap_raw = settings.get("imap_config")
    if not imap_raw or not isinstance(imap_raw, dict):
        logger.warning("IMAP config not set in bot_settings — cannot auto-login")
        return False

    try:
        imap_cfg = ImapConfig.from_dict(imap_raw)
    except (KeyError, TypeError) as e:
        logger.error("Invalid IMAP config in bot_settings: %s", e)
        return False

    logger.info("[%s] attempting auto-login...", platform)
    try:
        return await login_fn(credentials, imap_cfg)
    except Exception as e:
        logger.error("[%s] auto-login raised: %s", platform, e, exc_info=True)
        return False
