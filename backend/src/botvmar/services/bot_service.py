"""Multi-platform orchestrator.

Reads `platform_settings`, picks the platforms to run, and dispatches one
isolated cycle per platform. A failure in one adapter cannot abort the others.

Public surface kept stable for `worker.py` and `api.py`:
  - `run_cycle(triggered_by, shutdown_flag)` — top-level entry point
  - `posts_today()`, `replies_last_hour()` — legacy helpers (Yahoo-only,
     kept temporarily for any caller that still relies on them).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Iterable

from botvmar.config import runtime
from botvmar.config.platforms import PlatformConfig, load_enabled
from botvmar.db.repositories import activities
from botvmar.services.platform_runner import (
    _count_recent,  # re-exported below for backward compat
    run_platform_cycle,
)
from botvmar.utils.logger import get_logger

logger = get_logger("service.bot")


# ---------------------------------------------------------------------------
# Legacy helpers (Yahoo-only) — kept so existing imports don't break
# ---------------------------------------------------------------------------

async def replies_last_hour() -> int:
    return await _count_recent("yahoo_finance", "reply", "success", timedelta(hours=1))


async def posts_today() -> int:
    return await _count_recent("yahoo_finance", "post", "success", timedelta(days=1))


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def _run_one_safely(
    platform_config: PlatformConfig,
    *,
    triggered_by: str,
    shutdown_flag,
) -> None:
    """Wrap `run_platform_cycle` so an unexpected crash never propagates."""
    try:
        await run_platform_cycle(
            platform_config,
            triggered_by=triggered_by,
            shutdown_flag=shutdown_flag,
        )
    except Exception as e:
        # `run_platform_cycle` already catches PlatformError and unexpected
        # exceptions; this is a last-resort safety net for crashes happening
        # in the catch/finally blocks themselves.
        logger.critical(
            "[%s] orchestrator-level crash: %s",
            platform_config.platform, e, exc_info=True,
        )
        try:
            await activities.log(
                platform=platform_config.platform,
                type="error",
                status="failed",
                error_msg=f"orchestrator_crash: {str(e)[:900]}",
            )
        except Exception:
            pass


async def run_cycle(
    triggered_by: str = "schedule",
    shutdown_flag=lambda: False,
    only_platforms: Iterable[str] | None = None,
) -> None:
    """Run one cycle for every enabled platform, in parallel and in isolation.

    Parameters
    ----------
    triggered_by : "schedule" | "manual"
        Stored on each `bot_runs` row for analytics.
    shutdown_flag : callable returning bool
        Polled inside per-platform loops; set when a graceful stop is requested.
    only_platforms : iterable of str, optional
        Restrict the cycle to a subset (used by `/trigger-cycle/{platform}`).
    """
    settings = await runtime.load()
    if not settings.bot_enabled:
        logger.info("Bot disabled in settings — skipping cycle (master switch off)")
        await activities.log(
            type="scrape", status="skipped",
            error_msg="bot_enabled=false",
        )
        return

    platforms = await load_enabled()
    if only_platforms:
        wanted = {p.lower() for p in only_platforms}
        platforms = [p for p in platforms if p.platform in wanted]

    if not platforms:
        logger.info("No enabled platform — nothing to do")
        return

    logger.info(
        "Cycle start (trigger=%s) — platforms: %s",
        triggered_by, ", ".join(p.platform for p in platforms),
    )

    tasks = [
        asyncio.create_task(
            _run_one_safely(p, triggered_by=triggered_by, shutdown_flag=shutdown_flag),
            name=f"cycle:{p.platform}",
        )
        for p in platforms
    ]
    # `gather(return_exceptions=True)` is redundant given `_run_one_safely`,
    # but we keep it as a belt-and-braces guarantee.
    await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Cycle complete for %d platform(s)", len(platforms))
