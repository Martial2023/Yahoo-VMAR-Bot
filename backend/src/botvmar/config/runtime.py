"""Runtime configuration loaded from Postgres `BotSettings`.

The frontend (Next.js) writes to this table; the worker reads it at the start of
each cycle and on `/reload-config` API calls. Cached in-process between reloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from botvmar.db.repositories import settings as settings_repo
from botvmar.utils.logger import get_logger

logger = get_logger("config.runtime")


@dataclass
class RuntimeSettings:
    bot_enabled: bool = True
    mode: str = "both"  # "reply" | "post" | "both"
    ticker: str = "VMAR"
    check_interval_min: int = 120
    check_interval_max: int = 300
    max_replies_per_hour: int = 5
    max_posts_per_day: int = 3
    ai_model: str = "anthropic/claude-sonnet-4-20250514"
    ai_temperature: float = 0.7
    reply_prompt: str = ""
    post_prompt: str = ""
    alert_emails: list[str] = field(default_factory=list)


_cache: RuntimeSettings | None = None
# Snapshot of (mode, ticker, bot_enabled) we last INFO-logged. The worker
# reloads settings on every tick; logging a fresh INFO line each time is
# noise, so we downgrade to DEBUG when nothing observable changed.
_last_logged: tuple[str, str, bool] | None = None


async def load() -> RuntimeSettings:
    """Force-reload settings from Postgres and update the cache."""
    global _cache, _last_logged
    row = await settings_repo.get_settings()
    _cache = RuntimeSettings(
        bot_enabled=row["bot_enabled"],
        mode=row["mode"],
        ticker=row["ticker"],
        check_interval_min=row["check_interval_min"],
        check_interval_max=row["check_interval_max"],
        max_replies_per_hour=row["max_replies_per_hour"],
        max_posts_per_day=row["max_posts_per_day"],
        ai_model=row["ai_model"],
        ai_temperature=float(row["ai_temperature"]),
        reply_prompt=row["reply_prompt"],
        post_prompt=row["post_prompt"],
        alert_emails=list(row["alert_emails"] or []),
    )
    snapshot = (_cache.mode, _cache.ticker, _cache.bot_enabled)
    if snapshot != _last_logged:
        logger.info(
            "Runtime settings changed — mode=%s ticker=%s enabled=%s",
            _cache.mode, _cache.ticker, _cache.bot_enabled,
        )
        _last_logged = snapshot
    else:
        logger.debug("Runtime settings reloaded (unchanged)")
    return _cache


async def get() -> RuntimeSettings:
    """Return cached settings, loading on first access."""
    if _cache is None:
        return await load()
    return _cache
