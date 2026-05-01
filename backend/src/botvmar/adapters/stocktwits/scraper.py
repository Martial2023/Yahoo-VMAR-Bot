"""Scrape StockTwits message stream for a given ticker symbol."""

from __future__ import annotations

import hashlib
import re

from playwright.async_api import Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("scraper.stocktwits")

# StockTwits message IDs are numeric, embedded in data-testid="message-{id}"
_MSG_ID_RE = re.compile(r"message-(\d+)")

# Official / promotional accounts that should never receive a reply.
SKIP_AUTHORS = {"visionmarineir", "networkNewswire"}


def _generate_message_id(author: str, text: str) -> str:
    """Fallback ID when we cannot extract the native StockTwits message id."""
    raw = f"{author}:{text[:200]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def _navigate_to_stream(page: Page, ticker: str) -> bool:
    """Navigate to the StockTwits symbol page and wait for the message feed."""
    url = f"https://stocktwits.com/symbol/{ticker}"
    logger.info("Navigating to %s", url)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        logger.warning("Navigation to StockTwits failed: %s", e)
        return False

    # Wait for network to settle (SPA hydration)
    try:
        await page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        logger.debug("networkidle not reached — continuing anyway")

    await human_delay(3.0, 5.0)

    # Accept cookie / consent banners if any
    for consent_sel in [
        'button:has-text("Accept")',
        'button:has-text("I agree")',
        '[data-testid="consent-accept"]',
    ]:
        try:
            btn = page.locator(consent_sel).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await human_delay(1.0, 2.0)
                break
        except Exception:
            continue

    # Wait for at least one message in the feed
    try:
        await page.wait_for_selector(
            '[data-testid^="message-"]', timeout=20000,
        )
        return True
    except Exception:
        logger.warning("No messages found in feed after waiting")
        try:
            await page.screenshot(
                path=str(SCREENSHOTS_DIR / "stocktwits_no_messages.png"),
                full_page=True, timeout=10000,
            )
        except Exception:
            pass
        return False


async def scrape_messages(page: Page, ticker: str) -> list[dict]:
    """Scrape visible messages from the StockTwits stream.

    Returns a list of dicts with keys: id, author, text, date, likes,
    sentiment, comment_count, element_index, _selector.
    """
    try:
        if "stocktwits.com" not in page.url or f"/symbol/{ticker}" not in page.url.upper().replace(ticker.lower(), ticker):
            ok = await _navigate_to_stream(page, ticker)
            if not ok:
                return []
        else:
            # Already on the right page — just refresh the feed
            await human_delay(1.0, 2.0)

        # Progressive scroll to trigger lazy-loading
        for i in range(4):
            await page.evaluate("window.scrollBy(0, 600)")
            await human_delay(1.5, 3.0)
            logger.debug("Scroll %d/4 done", i + 1)

        # Scroll back to top so element indices are stable
        await page.evaluate("window.scrollTo(0, 0)")
        await human_delay(1.0, 2.0)

        # Locate all message containers
        selector = '[data-testid^="message-"]'
        messages_loc = page.locator(selector)
        count = await messages_loc.count()
        logger.info("Found %d messages in StockTwits feed", count)

        results: list[dict] = []
        for i in range(count):
            try:
                el = messages_loc.nth(i)

                # --- Message ID (from data-testid="message-12345") ---
                msg_id = ""
                try:
                    testid = await el.get_attribute("data-testid")
                    if testid:
                        m = _MSG_ID_RE.search(testid)
                        if m:
                            msg_id = m.group(1)
                except Exception:
                    pass

                # --- Author (username link with aria-label="Username") ---
                author = ""
                try:
                    user_el = el.locator('[aria-label="Username"]').first
                    txt = await user_el.text_content(timeout=1500)
                    author = (txt or "").strip()
                except Exception:
                    pass

                # --- Message text (RichTextMessage body) ---
                text = ""
                try:
                    body_el = el.locator(
                        '[class*="RichTextMessage_body"]'
                    ).first
                    txt = await body_el.text_content(timeout=2000)
                    text = (txt or "").strip()
                except Exception:
                    pass

                if not text:
                    continue

                # --- Timestamp ---
                date_str = ""
                try:
                    ts_el = el.locator(
                        '[aria-label="Time this message was posted"]'
                    ).first
                    txt = await ts_el.text_content(timeout=1000)
                    date_str = (txt or "").strip()
                except Exception:
                    pass

                # --- Sentiment (Bullish / Bearish badge) ---
                sentiment = ""
                try:
                    sent_el = el.locator(
                        '[aria-label="Message sentiment"]'
                    ).first
                    txt = await sent_el.text_content(timeout=1000)
                    sentiment = (txt or "").strip()
                except Exception:
                    pass

                # --- Like count ---
                likes = 0
                try:
                    like_el = el.locator(
                        '[aria-label="Like message"]'
                    ).first
                    txt = await like_el.text_content(timeout=1000)
                    if txt:
                        nums = re.findall(r"\d+", txt.strip())
                        if nums:
                            likes = int(nums[0])
                except Exception:
                    pass

                comment_id = msg_id or _generate_message_id(author, text)
                results.append({
                    "id": comment_id,
                    "author": author,
                    "text": text,
                    "date": date_str,
                    "likes": likes,
                    "sentiment": sentiment,
                    "comment_count": 0,
                    "element_index": i,
                    "_selector": selector,
                })
            except Exception as e:
                logger.debug("Error parsing message %d: %s", i, e)
                continue

        logger.info("Scraped %d messages total from StockTwits", len(results))
        return results

    except Exception as e:
        logger.error("Error scraping StockTwits: %s", e)
        try:
            await page.screenshot(
                path=str(SCREENSHOTS_DIR / "stocktwits_scrape_error.png"),
                timeout=10000,
            )
        except Exception:
            pass
        return []
