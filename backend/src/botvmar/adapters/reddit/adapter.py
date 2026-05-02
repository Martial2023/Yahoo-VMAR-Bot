"""Reddit adapter — Playwright-based scraper/poster for reddit.com.

Unlike the previous asyncpraw-based version, this adapter uses browser
automation (cookie-based auth via a saved session) to:

  1. Search Reddit for posts mentioning VMAR / Vision Marine
  2. Open each post and scrape its comments
  3. Reply to relevant comments via the Lexical rich-text editor

Since VMAR has no dedicated subreddit, the bot searches across all of Reddit
and engages with existing conversations rather than creating new posts.
"""

from __future__ import annotations

from playwright.async_api import Browser, Page, Playwright

from botvmar.adapters.base import (
    PlatformAdapter,
    PlatformAuthError,
    Post,
)
from botvmar.adapters.reddit.actions import comment_on_post, reply_to_comment
from botvmar.adapters.reddit.scraper import SKIP_AUTHORS, scrape_post_comments, search_posts
from botvmar.browser.session import create_browser_for
from botvmar.browser.stealth import human_delay
from botvmar.config.platforms import PlatformConfig
from botvmar.utils.logger import get_logger

logger = get_logger("adapter.reddit")

_SESSION_KEY = "reddit"


class RedditAdapter(PlatformAdapter):
    """Wraps Reddit scraping/replying as a ``PlatformAdapter``."""

    name = "reddit"
    display_name = "Reddit"

    def __init__(self, *, config: PlatformConfig) -> None:
        self._config = config
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    async def init(self) -> None:
        """Open Chromium with stealth + restore Reddit cookies."""
        self._pw, self._browser, _, self._page = await create_browser_for(
            _SESSION_KEY, headless=True,
        )
        if not await self._check_session():
            # Session expired — attempt auto-login if credentials are configured
            if await self._attempt_auto_login():
                # Reload browser with fresh session
                await self._browser.close()
                await self._pw.stop()
                self._pw, self._browser, _, self._page = await create_browser_for(
                    _SESSION_KEY, headless=True,
                )
                if not await self._check_session():
                    raise PlatformAuthError(
                        "Reddit auto-login saved session but it is not valid"
                    )
            else:
                raise PlatformAuthError(
                    "Reddit session expired and auto-login failed — "
                    "check credentials and IMAP config in the dashboard"
                )

    async def _attempt_auto_login(self) -> bool:
        if not self._config or not self._config.credentials:
            logger.warning("[reddit] no credentials configured — cannot auto-login")
            return False
        from botvmar.auth.auto_login import attempt_auto_login
        return await attempt_auto_login("reddit", self._config.credentials)

    async def _check_session(self) -> bool:
        """Quick probe: load Reddit and verify we are logged in."""
        if self._page is None:
            return False
        try:
            await self._page.goto(
                "https://www.reddit.com",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            await human_delay(3.0, 5.0)

            url = self._page.url

            if "/login" in url or "/register" in url:
                logger.warning("Reddit redirected to %s — not logged in", url)
                return False

            # Look for logged-in indicators (user menu, create post button, etc.)
            logged_in_selectors = [
                '#USER_DROPDOWN_ID',
                'button[aria-label="User menu"]',
                'a[href*="/submit"]',
                'faceplate-tracker[noun="create_post"]',
                '[id*="header-action"]',
                'header button:has(img)',
            ]
            for sel in logged_in_selectors:
                try:
                    if await self._page.locator(sel).first.is_visible(timeout=3000):
                        logger.info("Reddit session OK — logged in")
                        return True
                except Exception:
                    continue

            # No login redirect — assume OK
            logger.info("Reddit session appears valid (no login redirect)")
            return True

        except Exception as e:
            logger.error("Error checking Reddit session: %s", e)
            return False

    async def cleanup(self) -> None:
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
        """Search Reddit for VMAR posts and scrape their comments."""
        if self._page is None:
            raise RuntimeError("RedditAdapter.init() must be called first")

        cfg = self._config.config or {}
        search_queries: list[str] = list(cfg.get("searchQueries") or [ticker])
        max_posts: int = int(cfg.get("maxPostsPerSearch") or 5)

        # Step 1: Search for posts
        post_metas = await search_posts(
            self._page, search_queries, max_posts=max_posts,
        )
        if not post_metas:
            logger.info("[reddit] no posts found in search")
            return []

        # Step 2: Visit each post and scrape comments
        all_comments: list[Post] = []
        for meta in post_metas:
            await human_delay(3.0, 6.0)  # anti-ban: slow between posts
            raw_comments = await scrape_post_comments(
                self._page, meta["url"], max_comments=15,
            )
            for c in raw_comments:
                all_comments.append(self._to_post(c))

        logger.info(
            "[reddit] fetched %d comments across %d posts",
            len(all_comments), len(post_metas),
        )
        return all_comments

    async def reply_to(self, post: Post, text: str) -> bool:
        if self._page is None:
            raise RuntimeError("RedditAdapter.init() must be called first")

        post_url = post.raw.get("post_url")
        selector = post.raw.get("_comment_selector")
        index = post.raw.get("element_index")

        if not post_url or selector is None or index is None:
            logger.warning("Post %s missing DOM context — cannot reply", post.id)
            return False

        # Navigate to the post if we're not already there
        current = self._page.url.split("?")[0].split("#")[0]
        if current != post_url:
            try:
                await self._page.goto(
                    post_url, wait_until="domcontentloaded", timeout=60000,
                )
                await human_delay(3.0, 5.0)
            except Exception as e:
                logger.warning("Failed to navigate to %s: %s", post_url, e)
                return False

        # element_index == -1 means "comment on the post itself" (no comments)
        if index == -1:
            return await comment_on_post(self._page, text)

        return await reply_to_comment(self._page, selector, index, text)

    async def create_post(self, ticker: str, text: str) -> bool:
        # VMAR has no dedicated subreddit — creating posts is disabled.
        logger.debug("[reddit] create_post disabled (no dedicated subreddit)")
        return False

    def should_skip_author(self, author: str) -> bool:
        if not author:
            return True
        lower = author.lower().strip()
        if lower in SKIP_AUTHORS:
            return True
        # Skip the bot's own account
        own = (self._config.credentials or {}).get("username", "")
        if own and lower == str(own).strip().lower():
            return True
        return False

    @staticmethod
    def _to_post(raw: dict) -> Post:
        return Post(
            id=raw["id"],
            platform="reddit",
            author=raw.get("author", ""),
            text=raw.get("text", ""),
            url=raw.get("post_url"),
            created_at=None,
            likes=0,
            reply_count=0,
            raw={
                "post_url": raw.get("post_url"),
                "_comment_selector": raw.get("_comment_selector"),
                "element_index": raw.get("element_index"),
            },
        )


__all__ = ["RedditAdapter"]
