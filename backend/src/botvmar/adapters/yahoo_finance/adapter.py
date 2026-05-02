"""Yahoo Finance adapter — wraps the existing Playwright scraper/poster.

The underlying modules (`botvmar.scraper.comments` and `botvmar.poster.actions`)
are kept untouched so the original behaviour is preserved bit-for-bit. This
adapter only translates between their format and the `Post` dataclass used by
the orchestrator.
"""

from __future__ import annotations

from playwright.async_api import Browser, Page, Playwright

from botvmar.adapters.base import (
    PlatformAdapter,
    PlatformAuthError,
    Post,
)
from botvmar.browser.session import create_browser, refresh_session_if_needed
from botvmar.config.platforms import PlatformConfig
from botvmar.poster.actions import (
    SKIP_AUTHORS,
    post_new_comment,
    reply_to_comment,
    should_skip_author,
)
from botvmar.scraper.comments import scrape_comments
from botvmar.utils.logger import get_logger

logger = get_logger("adapter.yahoo")


class YahooFinanceAdapter(PlatformAdapter):
    """Wraps the original Yahoo Finance pipeline as a `PlatformAdapter`."""

    name = "yahoo_finance"
    display_name = "Yahoo Finance"

    def __init__(self, *, config: PlatformConfig | None = None, headless: bool = True) -> None:
        self._config = config
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    async def init(self) -> None:
        """Open Chromium with stealth + restore Yahoo cookies."""
        self._pw, self._browser, _, self._page = await create_browser(
            headless=self._headless
        )
        if not await refresh_session_if_needed(self._page):
            # Session expired — attempt auto-login if credentials are configured
            if await self._attempt_auto_login():
                # Reload browser with the fresh session
                await self._browser.close()
                await self._pw.stop()
                self._pw, self._browser, _, self._page = await create_browser(
                    headless=self._headless
                )
                if not await refresh_session_if_needed(self._page):
                    raise PlatformAuthError(
                        "Yahoo auto-login saved session but it is not valid"
                    )
            else:
                raise PlatformAuthError(
                    "Yahoo session expired and auto-login failed — "
                    "check credentials and IMAP config in the dashboard"
                )

    async def _attempt_auto_login(self) -> bool:
        """Try auto-login using credentials from the dashboard."""
        if not self._config or not self._config.credentials:
            logger.warning("[yahoo] no credentials configured — cannot auto-login")
            return False
        from botvmar.auth.auto_login import attempt_auto_login
        return await attempt_auto_login("yahoo_finance", self._config.credentials)

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
            raise RuntimeError("YahooFinanceAdapter.init() must be called first")

        raw_comments = await scrape_comments(self._page, ticker)
        return [self._to_post(c) for c in raw_comments]

    async def reply_to(self, post: Post, text: str) -> bool:
        if self._page is None:
            raise RuntimeError("YahooFinanceAdapter.init() must be called first")

        selector = post.raw.get("_selector")
        index = post.raw.get("element_index")
        if selector is None or index is None:
            logger.warning("Post %s missing DOM context — cannot reply", post.id)
            return False

        return await reply_to_comment(self._page, selector, index, text)

    async def create_post(self, ticker: str, text: str) -> bool:
        if self._page is None:
            raise RuntimeError("YahooFinanceAdapter.init() must be called first")

        return await post_new_comment(self._page, ticker, text)

    def should_skip_author(self, author: str) -> bool:
        """Use the existing Yahoo skip list (official VMAR accounts)."""
        return should_skip_author(author)

    @staticmethod
    def _to_post(raw: dict) -> Post:
        """Convert a `scrape_comments()` dict to the normalized `Post` shape.

        The DOM context (`_selector`, `element_index`) is preserved in
        `Post.raw` because Yahoo replies require re-locating the element on
        the live page.
        """
        return Post(
            id=raw["id"],
            platform="yahoo_finance",
            author=raw.get("author", ""),
            text=raw.get("text", ""),
            url=None,
            created_at=None,
            likes=int(raw.get("likes") or 0),
            reply_count=int(raw.get("comment_count") or 0),
            raw={
                "_selector": raw.get("_selector"),
                "element_index": raw.get("element_index"),
                "date_str": raw.get("date", ""),
            },
        )


__all__ = ["YahooFinanceAdapter", "SKIP_AUTHORS"]
