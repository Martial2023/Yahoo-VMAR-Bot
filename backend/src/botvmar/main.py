"""Entry point — runs the worker loop and the FastAPI server in the same process.

  python -m botvmar.main
"""

from __future__ import annotations

import asyncio
import signal
import sys

import uvicorn

from botvmar import worker
from botvmar.api import app
from botvmar.config.env import API_HOST, API_PORT
from botvmar.db.pool import close_pool, init_pool
from botvmar.state import shutdown_event, trigger_event
from botvmar.utils.logger import get_logger

logger = get_logger("main")


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    def _handle(signum: int) -> None:
        logger.info("Received signal %d — initiating graceful shutdown", signum)
        shutdown_event.set()
        trigger_event.set()  # wake worker out of its sleep

    if sys.platform == "win32":
        # add_signal_handler is unsupported on Windows event loops.
        signal.signal(signal.SIGINT, lambda s, f: _handle(s))
        signal.signal(signal.SIGTERM, lambda s, f: _handle(s))
    else:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle, sig)


async def _run_api() -> None:
    """Start uvicorn programmatically so it shares our event loop."""
    config = uvicorn.Config(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=False,
        lifespan="off",
    )
    server = uvicorn.Server(config)

    server_task = asyncio.create_task(server.serve())
    await shutdown_event.wait()
    server.should_exit = True
    await server_task


async def _async_main() -> None:
    await init_pool()
    _install_signal_handlers(asyncio.get_running_loop())

    try:
        await asyncio.gather(
            worker.run(),
            _run_api(),
        )
    finally:
        await close_pool()
        logger.info("Process exited cleanly")


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    """" Lunchingr the main function when running this file directly. """
    main()
