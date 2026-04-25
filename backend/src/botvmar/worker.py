"""Bot worker — runs cycles on a schedule, reactively triggered by API calls.

Coordination with the FastAPI process is done via shared `asyncio.Event` objects
exposed in `botvmar.state` (set/cleared by the API endpoints).
"""

from __future__ import annotations

import asyncio
import random

from botvmar.config import runtime
from botvmar.services.bot_service import run_cycle
from botvmar.state import shutdown_event, trigger_event
from botvmar.utils.logger import get_logger
from botvmar.utils.notifier import notify

logger = get_logger("worker")


def _shutdown() -> bool:
    return shutdown_event.is_set()


async def _wait_or_trigger(seconds: float) -> str:
    """Sleep for `seconds`, but wake early on trigger or shutdown.

    Returns: "trigger" | "shutdown" | "timeout"
    """
    trigger_task = asyncio.create_task(trigger_event.wait())
    shutdown_task = asyncio.create_task(shutdown_event.wait())
    sleep_task = asyncio.create_task(asyncio.sleep(seconds))

    done, pending = await asyncio.wait(
        {trigger_task, shutdown_task, sleep_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()

    if shutdown_task in done:
        return "shutdown"
    if trigger_task in done:
        return "trigger"
    return "timeout"


async def run() -> None:
    """Main worker loop."""
    settings = await runtime.load()
    logger.info("=" * 50)
    logger.info("  Yahoo Finance VMAR Bot — Worker started")
    logger.info("  Mode: %s | Ticker: %s | Enabled: %s", settings.mode, settings.ticker, settings.bot_enabled)
    logger.info("=" * 50)

    await notify("Bot worker started", level="info")

    cycle_count = 0
    triggered_by = "schedule"

    while not _shutdown():
        cycle_count += 1
        logger.info("--- Cycle %d starting (trigger=%s) ---", cycle_count, triggered_by)

        try:
            await run_cycle(triggered_by=triggered_by, shutdown_flag=_shutdown)
        except Exception as e:
            logger.error("Unhandled error in cycle %d: %s", cycle_count, e, exc_info=True)
            await notify(f"Worker crashed in cycle {cycle_count}: {e}", level="critical")

        if _shutdown():
            break

        # Reload settings to pick up timing changes
        settings = await runtime.load()
        wait = random.uniform(settings.check_interval_min, settings.check_interval_max)
        logger.info("Cycle %d complete. Next cycle in %.0fs (or on trigger)...", cycle_count, wait)

        # Reset trigger before sleeping so we react only to NEW triggers
        trigger_event.clear()
        reason = await _wait_or_trigger(wait)
        triggered_by = "manual" if reason == "trigger" else "schedule"
        if reason == "trigger":
            logger.info("Manual trigger received — running cycle now")

    logger.info("Worker shutting down...")
    await notify("Bot worker stopped", level="info")
