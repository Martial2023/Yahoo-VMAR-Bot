"""Scrape Reddit for VMAR-related posts and their comments via Playwright.

Flow
----
1. Navigate to Reddit search: ``/search/?q=VMAR+Vision+Marine&type=posts``
2. Collect post URLs from search results (deduplication by URL)
3. Filter out posts not related to VMAR / Vision Marine (stocks, EV boats…)
4. For each post, navigate to it and scrape top-level comments
5. If a post has no comments, return the post itself as a reply target
6. Return items as dicts with DOM context for later reply

Anti-ban
--------
- Long delays between page navigations (3-8 s)
- Random scroll behaviour before interacting
- Limited number of posts visited per cycle (configurable, default 5)
- No continuous scraping — only called when the schedule fires
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import quote_plus

from playwright.async_api import Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("scraper.reddit")

# Official / bot accounts that should never receive a reply.
SKIP_AUTHORS = {"automoderator", "[deleted]", ""}

# Keywords that indicate a post is actually about VMAR the stock / Vision Marine
_RELEVANCE_KEYWORDS = [
    "vmar", "vision marine", "vision-marine", "electric boat",
    "bateau électrique", "e1", "stock", "nasdaq", "shares",
    "marine technologies", "pennystocks", "penny stock",
]

_COMMENT_ID_RE = re.compile(r"t1_([a-z0-9]+)")


def _generate_comment_id(author: str, text: str) -> str:
    """Fallback ID when we cannot extract the native Reddit comment id."""
    raw = f"{author}:{text[:200]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def _safe_screenshot(page: Page, name: str) -> None:
    try:
        await page.screenshot(path=str(SCREENSHOTS_DIR / name), timeout=10000)
    except Exception:
        pass


async def search_posts(
    page: Page,
    search_queries: list[str],
    *,
    max_posts: int = 5,
) -> list[dict]:
    """Search Reddit for posts matching *search_queries*. Return post metadata.

    Each dict has keys: ``url``, ``title``.
    Capped at *max_posts* results (across all queries, deduped).
    """
    seen_urls: set[str] = set()
    posts: list[dict] = []

    for query in search_queries:
        if len(posts) >= max_posts:
            break

        encoded = quote_plus(query)
        url = f"https://www.reddit.com/search/?q={encoded}&type=posts&sort=new"
        logger.info("Reddit search: %s", url)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning("Reddit search navigation failed for '%s': %s", query, e)
            continue

        await human_delay(3.0, 5.0)

        # Light scroll to trigger lazy-loading
        for _ in range(2):
            await page.evaluate("window.scrollBy(0, 400)")
            await human_delay(1.5, 2.5)

        # Collect post links from search results.
        # Reddit search results contain links to /r/<sub>/comments/<id>/...
        link_sel = 'a[href*="/comments/"]'
        links = page.locator(link_sel)
        count = await links.count()
        logger.info("Found %d post links in search results for '%s'", count, query)

        for i in range(count):
            if len(posts) >= max_posts:
                break
            try:
                href = await links.nth(i).get_attribute("href")
                if not href:
                    continue
                # Normalise to full URL
                if href.startswith("/"):
                    href = f"https://www.reddit.com{href}"
                # Remove query params / hash
                href = href.split("?")[0].split("#")[0]
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Try to grab the title text from the link
                title = ""
                try:
                    title = (await links.nth(i).text_content(timeout=2000) or "").strip()
                except Exception:
                    pass

                # Filter: skip posts whose title+URL show no VMAR relevance
                haystack = (title + " " + href).lower()
                if not any(kw in haystack for kw in _RELEVANCE_KEYWORDS):
                    logger.debug("Skipping irrelevant post: %s", title[:80] or href)
                    continue

                posts.append({"url": href, "title": title})
            except Exception:
                continue

        await human_delay(2.0, 4.0)

    logger.info("Collected %d unique post URLs from Reddit search", len(posts))
    return posts


async def scrape_post_comments(
    page: Page,
    post_url: str,
    *,
    max_comments: int = 15,
) -> list[dict]:
    """Navigate to *post_url* and scrape top-level comments.

    Returns a list of dicts with keys: ``id``, ``author``, ``text``,
    ``post_url``, ``element_index``, ``_comment_selector``.
    """
    logger.info("Opening Reddit post: %s", post_url)
    try:
        await page.goto(post_url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logger.warning("Failed to open Reddit post %s: %s", post_url, e)
        return []

    await human_delay(3.0, 6.0)

    # Dismiss cookie / consent banners
    for consent_sel in [
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'button:has-text("Accepter")',
        'button:has-text("Tout accepter")',
    ]:
        try:
            btn = page.locator(consent_sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await human_delay(1.0, 2.0)
                break
        except Exception:
            continue

    # --- Scrape the post itself (OP) as a reply target ---
    # If the post has few/no comments, the bot can comment directly on it.
    post_author = ""
    post_text = ""
    try:
        # Post author: <shreddit-post> has an "author" attribute
        post_el = page.locator("shreddit-post").first
        post_author = (await post_el.get_attribute("author") or "").strip()
        # Post body: inside the post element
        for sel in [
            'div[slot="text-body"]',
            'div[data-post-click-location="text-body"]',
            '[id*="post-rtjson-content"]',
            'h1',
        ]:
            try:
                el = page.locator(sel).first
                txt = await el.text_content(timeout=2000)
                if txt and txt.strip():
                    post_text = txt.strip()
                    break
            except Exception:
                continue
        # Fallback: use the page title
        if not post_text:
            post_text = (await page.title() or "").strip()
    except Exception as e:
        logger.debug("Could not scrape post OP: %s", e)

    # Scroll to load more comments
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 500)")
        await human_delay(1.5, 3.0)

    # Scroll back up
    await page.evaluate("window.scrollTo(0, 0)")
    await human_delay(1.0, 2.0)

    # Reddit uses <shreddit-comment> custom elements for comments
    comment_selector = "shreddit-comment"
    comments_loc = page.locator(comment_selector)
    count = await comments_loc.count()
    logger.info("Found %d comments on post %s", count, post_url)

    results: list[dict] = []

    # If the post has no comments, return the post itself as a reply target.
    # element_index=-1 signals "comment on the post" (not reply to a comment).
    if count == 0 and post_text and post_author:
        if post_author.lower() not in SKIP_AUTHORS:
            pid = _generate_comment_id(post_author, post_text)
            results.append({
                "id": f"reddit_post_{pid}",
                "author": post_author,
                "text": post_text,
                "post_url": post_url,
                "element_index": -1,          # signals: comment on post, not reply to comment
                "_comment_selector": "post",
            })
            logger.info("No comments — post itself queued as reply target")

    for i in range(min(count, max_comments)):
        try:
            el = comments_loc.nth(i)

            # --- Comment ID (from thing-id="t1_xxx" attribute) ---
            comment_id = ""
            try:
                thing_id = await el.get_attribute("thingid")
                if thing_id:
                    m = _COMMENT_ID_RE.search(thing_id)
                    comment_id = m.group(1) if m else thing_id
            except Exception:
                pass

            # --- Author ---
            author = ""
            try:
                author = (await el.get_attribute("author") or "").strip()
            except Exception:
                pass

            if not author or author.lower() in SKIP_AUTHORS:
                continue

            # --- Comment text ---
            text = ""
            try:
                # The comment body is inside a <div> with slot="comment"
                # or inside an element with id containing "comment-content"
                body_selectors = [
                    'div[slot="comment"] p',
                    'div[id*="comment-content"]',
                    '.md p',
                    'p',
                ]
                for body_sel in body_selectors:
                    body_el = el.locator(body_sel).first
                    txt = await body_el.text_content(timeout=2000)
                    if txt and txt.strip():
                        text = txt.strip()
                        break
            except Exception:
                pass

            if not text:
                continue

            cid = comment_id or _generate_comment_id(author, text)
            results.append({
                "id": f"reddit_t1_{cid}",
                "author": author,
                "text": text,
                "post_url": post_url,
                "element_index": i,
                "_comment_selector": comment_selector,
            })

        except Exception as e:
            logger.debug("Error parsing Reddit comment %d: %s", i, e)
            continue

    logger.info("Scraped %d comments from Reddit post", len(results))
    return results
