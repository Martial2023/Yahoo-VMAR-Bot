"""Platform adapters — one module per social/finance platform.

Each adapter implements the `PlatformAdapter` interface defined in `base.py`
and exposes a uniform API to the orchestrator (`services.bot_service`).

Available adapters:
  - yahoo_finance : Yahoo Finance community pages (Playwright + cookies)
  - reddit        : Reddit subreddits (official OAuth2 API)
  - stocktwits    : (planned) StockTwits messages (scraping)
  - seeking_alpha : (planned) Seeking Alpha articles (scraping)
  - investing     : (planned) Investing.com forums (scraping)
"""

from botvmar.adapters.base import (
    Post,
    PlatformAdapter,
    PlatformError,
    PlatformAuthError,
    PlatformRateLimitError,
)

__all__ = [
    "Post",
    "PlatformAdapter",
    "PlatformError",
    "PlatformAuthError",
    "PlatformRateLimitError",
]
