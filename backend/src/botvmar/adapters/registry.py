"""Maps a platform name (DB column value) to its adapter class.

Adding a new platform = adding one entry here. The orchestrator calls
`build_adapter(name, config)` and never imports adapter modules directly.
"""

from __future__ import annotations

from typing import Callable

from botvmar.adapters.base import PlatformAdapter
from botvmar.config.platforms import PlatformConfig
from botvmar.utils.logger import get_logger

logger = get_logger("adapter.registry")


def _build_yahoo_finance(config: PlatformConfig) -> PlatformAdapter:
    # Local import to avoid loading Playwright at module import time.
    from botvmar.adapters.yahoo_finance import YahooFinanceAdapter
    return YahooFinanceAdapter(config=config)


def _build_stocktwits(config: PlatformConfig) -> PlatformAdapter:
    from botvmar.adapters.stocktwits import StockTwitsAdapter
    return StockTwitsAdapter(config=config)


def _build_reddit(config: PlatformConfig) -> PlatformAdapter:
    # The Reddit adapter is added in Phase 3. Raising at build-time means an
    # operator who flips `enabled = true` before the adapter exists gets a
    # clear log entry instead of a silent no-op cycle.
    try:
        from botvmar.adapters.reddit import RedditAdapter
    except ImportError as e:
        raise RuntimeError(f"Reddit adapter not available yet: {e}") from e
    return RedditAdapter(config=config)



_REGISTRY: dict[str, Callable[[PlatformConfig], PlatformAdapter]] = {
    "yahoo_finance": _build_yahoo_finance,
    "stocktwits": _build_stocktwits,
    "reddit": _build_reddit,
}


def build_adapter(config: PlatformConfig) -> PlatformAdapter | None:
    """Instantiate the adapter for `config.platform`. Returns None if unknown."""
    factory = _REGISTRY.get(config.platform)
    if factory is None:
        logger.warning("Unknown platform '%s' — no adapter registered", config.platform)
        return None
    try:
        return factory(config)
    except Exception as e:
        logger.error("Failed to build adapter for '%s': %s", config.platform, e, exc_info=True)
        return None


def known_platforms() -> list[str]:
    return list(_REGISTRY.keys())
