"""Shared asyncio state between the worker and the API."""

from __future__ import annotations

import asyncio

# Set by the API's /trigger-cycle to wake the worker mid-sleep.
trigger_event: asyncio.Event = asyncio.Event()

# Set by the main process on SIGTERM/SIGINT to stop the worker gracefully.
shutdown_event: asyncio.Event = asyncio.Event()

# Platforms requested via /trigger-cycle/{platform}. Empty set means "all
# enabled platforms" (the no-arg /trigger-cycle endpoint).
manual_platforms: set[str] = set()
manual_lock: asyncio.Lock = asyncio.Lock()


async def queue_manual_trigger(platform: str | None = None) -> None:
    """Queue a manual cycle and wake the worker.

    `platform=None` triggers all enabled platforms; otherwise only that one
    is run. Multiple calls before the worker wakes accumulate.
    """
    async with manual_lock:
        if platform is not None:
            manual_platforms.add(platform)
    trigger_event.set()


async def consume_manual_platforms() -> set[str]:
    """Atomically read and clear the queued manual platforms set."""
    async with manual_lock:
        platforms = manual_platforms.copy()
        manual_platforms.clear()
    return platforms
