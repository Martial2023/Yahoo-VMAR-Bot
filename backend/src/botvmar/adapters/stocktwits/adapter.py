"""StockTwits adapter — Playwright-based scraper/poster for stocktwits.com.

Follows the same pattern as the Yahoo Finance adapter: cookie-based auth
via a saved browser session, stealth Chromium, human-like delays.
"""

from __future__ import annotations

from playwright.async_api import Browser, Page, Playwright

from botvmar.adapters.base import (
    PlatformAdapter,
    PlatformAuthError,
    Post,
)
from botvmar.adapters.stocktwits.actions import post_new_message, reply_to_message
from botvmar.adapters.stocktwits.scraper import SKIP_AUTHORS, scrape_messages
from botvmar.browser.session import create_browser_for
from botvmar.utils.logger import get_logger

logger = get_logger("adapter.stocktwits")

_SESSION_KEY = "stocktwits"


class StockTwitsAdapter(PlatformAdapter):
    """Wraps StockTwits scraping/posting as a `PlatformAdapter`."""

    name = "stocktwits"
    display_name = "StockTwits"

    def __init__(self, *, headless: bool = True) -> None:
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    async def init(self) -> None:
        """Open Chromium with stealth + restore StockTwits cookies."""
        self._pw, self._browser, _, self._page = await create_browser_for(
            _SESSION_KEY, headless=self._headless,
        )
        # Validate session: navigate to StockTwits and check we're logged in
        if not await self._check_session():
            raise PlatformAuthError(
                "StockTwits session expired — re-run scripts/login_stocktwits.py"
            )

    async def _check_session(self) -> bool:
        """Quick probe: load StockTwits and verify we are logged in."""
        if self._page is None:
            return False
        try:
            await self._page.goto(
                "https://stocktwits.com",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            from botvmar.browser.stealth import human_delay
            await human_delay(3.0, 5.0)

            url = self._page.url

            # If redirected to login/signup page, session is invalid
            if "/login" in url or "/signup" in url:
                logger.warning("StockTwits redirected to %s — not logged in", url)
                return False

            # Check for a logged-in indicator (compose area, user menu, etc.)
            logged_in_selectors = [
                '[data-testid="compose-input"]',
                'div[contenteditable="true"]',
                '[class*="ComposeForm"]',
                '[class*="UserMenu"]',
                '[class*="avatar"]',
            ]
            for sel in logged_in_selectors:
                try:
                    if await self._page.locator(sel).first.is_visible(timeout=3000):
                        logger.info("StockTwits session OK — logged in")
                        return True
                except Exception:
                    continue

            # No login redirect and page loaded — assume OK
            logger.info("StockTwits session appears valid (no login redirect)")
            return True

        except Exception as e:
            logger.error("Error checking StockTwits session: %s", e)
            return False

    async def cleanup(self) -> None:
        """Close browser & playwright. Never raises."""
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                logger.debug("Browser close error (ignored): %s", e)
            self._browser = None
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception as e:
                logger.debug("Playwright stop error (ignored): %s", e)
            self._pw = None
        self._page = None

    async def fetch_posts(self, ticker: str) -> list[Post]:
        if self._page is None:
            raise RuntimeError("StockTwitsAdapter.init() must be called first")
        raw_messages = await scrape_messages(self._page, ticker)
        return [self._to_post(m) for m in raw_messages]

    async def reply_to(self, post: Post, text: str) -> bool:
        if self._page is None:
            raise RuntimeError("StockTwitsAdapter.init() must be called first")

        selector = post.raw.get("_selector")
        index = post.raw.get("element_index")
        if selector is None or index is None:
            logger.warning("Post %s missing DOM context — cannot reply", post.id)
            return False

        return await reply_to_message(self._page, selector, index, text)

    async def create_post(self, ticker: str, text: str) -> bool:
        if self._page is None:
            raise RuntimeError("StockTwitsAdapter.init() must be called first")
        return await post_new_message(self._page, ticker, text)

    def should_skip_author(self, author: str) -> bool:
        """Skip official VMAR-related accounts on StockTwits."""
        lower = author.lower().strip()
        return any(skip in lower for skip in SKIP_AUTHORS)

    @staticmethod
    def _to_post(raw: dict) -> Post:
        """Convert a scraped message dict to the normalized `Post` shape."""
        return Post(
            id=raw["id"],
            platform="stocktwits",
            author=raw.get("author", ""),
            text=raw.get("text", ""),
            url=f"https://stocktwits.com/message/{raw['id']}" if raw.get("id", "").isdigit() else None,
            created_at=None,
            likes=int(raw.get("likes") or 0),
            reply_count=int(raw.get("comment_count") or 0),
            raw={
                "_selector": raw.get("_selector"),
                "element_index": raw.get("element_index"),
                "date_str": raw.get("date", ""),
                "sentiment": raw.get("sentiment", ""),
            },
        )


__all__ = ["StockTwitsAdapter"]
