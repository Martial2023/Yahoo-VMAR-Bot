"""Bot worker — slot-based scheduler that runs platform cycles.

Loop semantics
--------------
The worker ticks every `_TICK_SECONDS`. On each tick it:

  1. Drains any manual triggers (from `/trigger-cycle` or `/trigger-cycle/{p}`)
     and runs them immediately.
  2. Reads the master kill switch (`bot_settings.bot_enabled`).
  3. For every enabled platform, checks whether `now` falls inside one of
     its scheduled slots' jitter window AND no run has started in that
     window yet. Eligible platforms are run in parallel via the
     orchestrator (`bot_service.run_cycle`).

Coordination with the FastAPI process is done via shared `asyncio.Event` and
the helpers in `botvmar.state`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from botvmar.config import runtime
from botvmar.config.env import RUN_ON_STARTUP
from botvmar.config.platforms import load_enabled
from botvmar.db.repositories import runs as runs_repo
from botvmar.scheduling.slots import is_slot_due, next_slot_after
from botvmar.services.bot_service import run_cycle
from botvmar.state import (
    consume_manual_platforms,
    shutdown_event,
    trigger_event,
)
from botvmar.utils.logger import get_logger
from botvmar.utils.notifier import notify

logger = get_logger("worker")

# How often the scheduler wakes up to evaluate slots. 30 seconds gives a
# generous buffer for any slot whose jitter window is at least 1 minute.
_TICK_SECONDS = 30


def _shutdown() -> bool:
    return shutdown_event.is_set()


async def _wait(seconds: float) -> str:
    """Sleep up to `seconds`, but wake early on trigger or shutdown.

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


async def _due_platforms() -> list[str]:
    """Return the platforms whose schedule fires now."""
    configs = await load_enabled()
    if not configs:
        return []

    now = datetime.utcnow()
    due: list[str] = []
    for cfg in configs:
        if not cfg.schedule_slots:
            # No slots configured → never fires automatically (manual only).
            continue
        last_run = await runs_repo.last_started_at(cfg.platform)
        if is_slot_due(cfg.schedule_slots, now, last_run, cfg.schedule_jitter_min):
            due.append(cfg.platform)
    return due


async def _seconds_until_next_slot() -> float:
    """Compute a sensible sleep duration before the next slot tick.

    Caps at `_TICK_SECONDS * 4` so the worker always re-evaluates within
    ~2 minutes (catches config changes made via `/reload-config`).
    """
    configs = await load_enabled()
    now = datetime.utcnow()
    next_starts: list[datetime] = []
    for cfg in configs:
        ns = next_slot_after(cfg.schedule_slots, now)
        if ns is not None:
            next_starts.append(ns)
    if not next_starts:
        return _TICK_SECONDS

    delta = (min(next_starts) - now).total_seconds()
    return max(_TICK_SECONDS, min(delta, _TICK_SECONDS * 4))


async def run() -> None:
    """Main worker loop."""
    settings = await runtime.load()
    logger.info("=" * 60)
    logger.info("  BotVMAR worker started — slot-based scheduler")
    logger.info("  Master enabled=%s | tick=%ds", settings.bot_enabled, _TICK_SECONDS)
    logger.info("=" * 60)

    await notify("Bot worker started", level="info")

    # Clear any stale trigger from a previous process lifetime.
    trigger_event.clear()

    # --- Run one cycle immediately on startup (all enabled platforms) ---
    if RUN_ON_STARTUP and settings.bot_enabled:
        logger.info("RUN_ON_STARTUP=true — running initial cycle for all enabled platforms")
        try:
            await run_cycle(
                triggered_by="startup",
                shutdown_flag=_shutdown,
            )
        except Exception as e:
            logger.error("Startup cycle failed: %s", e, exc_info=True)
            await notify(f"Startup cycle crashed: {e}", level="critical")

    while not _shutdown():
        #1. Manual trigger
        if trigger_event.is_set():
            trigger_event.clear()
            manual = await consume_manual_platforms()
            only = list(manual) if manual else None
            logger.info(
                "Manual trigger — running %s",
                ", ".join(only) if only else "all enabled platforms",
            )
            try:
                await run_cycle(
                    triggered_by="manual",
                    shutdown_flag=_shutdown,
                    only_platforms=only,
                )
            except Exception as e:
                logger.error("Unhandled error during manual cycle: %s", e, exc_info=True)
                await notify(f"Worker crashed in manual cycle: {e}", level="critical")

            if _shutdown():
                break
            continue

        #2. Master kill switch
        try:
            settings = await runtime.load()
        except Exception as e:
            logger.error("Failed to reload settings: %s", e, exc_info=True)
            await _wait(_TICK_SECONDS)
            continue

        if not settings.bot_enabled:
            logger.debug("Master switch off — sleeping %ds", _TICK_SECONDS)
            await _wait(_TICK_SECONDS)
            continue

        #3. Slot-based scheduling
        try:
            due = await _due_platforms()
        except Exception as e:
            logger.error("Failed to evaluate due platforms: %s", e, exc_info=True)
            await _wait(_TICK_SECONDS)
            continue

        if due:
            logger.info("Slot fired for: %s", ", ".join(due))
            try:
                await run_cycle(
                    triggered_by="schedule",
                    shutdown_flag=_shutdown,
                    only_platforms=due,
                )
            except Exception as e:
                logger.error("Unhandled error during scheduled cycle: %s", e, exc_info=True)
                await notify(f"Worker crashed in scheduled cycle: {e}", level="critical")

            if _shutdown():
                break

        #4. Sleep until next slot
        sleep_for = await _seconds_until_next_slot()
        logger.debug("Next tick in %.0fs", sleep_for)
        await _wait(sleep_for)

    logger.info("Worker shutting down...")
    await notify("Bot worker stopped", level="info")