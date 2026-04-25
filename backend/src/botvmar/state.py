"""Shared asyncio events between the worker and the API."""

import asyncio

# Set by the API's /trigger-cycle to wake the worker mid-sleep.
trigger_event: asyncio.Event = asyncio.Event()

# Set by the main process on SIGTERM/SIGINT to stop the worker gracefully.
shutdown_event: asyncio.Event = asyncio.Event()
