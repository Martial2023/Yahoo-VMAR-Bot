"""Playwright actions — reply to a comment, post a new comment."""

from __future__ import annotations

from playwright.async_api import Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("poster")


async def _safe_screenshot(page: Page, name: str) -> None:
    """Take a screenshot, silently ignoring errors (closed page, etc.)."""
    try:
        await page.screenshot(
            path=str(SCREENSHOTS_DIR / name),
            timeout=10000,
        )
    except Exception:
        pass


async def reply_to_comment(
    page: Page,
    comment_selector: str,
    comment_index: int,
    reply_text: str,
) -> bool:
    """Click reply on a specific comment, type, submit. Returns success."""
    try:
        comment_el = page.locator(comment_selector).nth(comment_index)

        # Vérifier que l'élément est visible avant d'agir
        try:
            await comment_el.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            logger.warning("Comment %d not visible/accessible", comment_index)
            return False

        # Le bouton "Comment" sous chaque post ouvre la zone de réponse.
        reply_button_selectors = [
            '[data-testid="comment-action"]',
            'button:has-text("Comment")',
            'button:has-text("Reply")',
        ]
        clicked = False
        for btn_sel in reply_button_selectors:
            try:
                btn = comment_el.locator(btn_sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            logger.warning("Could not find reply button for comment %d", comment_index)
            await _safe_screenshot(page, f"no_reply_btn_{comment_index}.png")
            return False

        await human_delay(1.0, 2.0)

        # Reply text input
        reply_input_selectors = [
            '[data-testid="reply-input"]',
            'textarea[placeholder*="reply" i]',
            '.reply-input textarea',
            'div[contenteditable="true"]',
            'textarea[class*="reply"]',
        ]
        typed = False
        for input_sel in reply_input_selectors:
            try:
                input_el = page.locator(input_sel).first
                if await input_el.is_visible(timeout=5000):
                    await input_el.click()
                    await human_delay(0.3, 0.7)
                    await input_el.type(reply_text, delay=80)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not find reply input field for comment %d", comment_index)
            await _safe_screenshot(page, f"no_reply_input_{comment_index}.png")
            return False

        await human_delay(1.0, 2.0)

        # Submit reply button
        submit_selectors = [
            'button:has-text("Post")',
            'button:has-text("Submit")',
            '[data-testid="submit-reply"]',
            'button[type="submit"]',
        ]
        submitted = False
        for submit_sel in submit_selectors:
            try:
                submit_btn = page.locator(submit_sel).first
                if await submit_btn.is_visible(timeout=3000):
                    await submit_btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            logger.warning("Could not find submit button for reply")
            await _safe_screenshot(page, f"no_submit_btn_{comment_index}.png")
            return False

        await human_delay(2.0, 4.0)
        logger.info("Reply posted to comment %d: %s...", comment_index, reply_text[:60])
        return True

    except Exception as e:
        logger.error("Error replying to comment %d: %s", comment_index, e)
        await _safe_screenshot(page, f"reply_error_{comment_index}.png")
        return False


async def post_new_comment(page: Page, ticker: str, text: str) -> bool:
    """Post a brand-new comment on the community page."""
    try:
        if "community" not in page.url.lower():
            url = f"https://finance.yahoo.com/quote/{ticker}/community"
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await human_delay(4.0, 6.0)

        # Main comment input — le champ "What's on your mind?"
        comment_input_selectors = [
            '[data-testid="comment-input"]',
            'textarea[placeholder*="mind" i]',
            'textarea[placeholder*="comment" i]',
            'textarea[placeholder*="Share" i]',
            'div[data-placeholder*="mind" i]',
            'div[contenteditable="true"]',
        ]
        typed = False
        for input_sel in comment_input_selectors:
            try:
                input_el = page.locator(input_sel).first
                if await input_el.is_visible(timeout=5000):
                    await input_el.click()
                    await human_delay(0.5, 1.0)
                    await input_el.type(text, delay=80)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not find comment input field")
            await _safe_screenshot(page, "no_comment_input.png")
            return False

        await human_delay(1.5, 3.0)

        # Submit button (la flèche ou bouton "Post")
        submit_selectors = [
            'button[data-testid="submit-comment"]',
            'button:has-text("Post")',
            'button:has-text("Submit")',
            'button[type="submit"]',
            # La flèche d'envoi visible sur le screenshot
            'button[aria-label*="send" i]',
            'button[aria-label*="post" i]',
        ]
        submitted = False
        for submit_sel in submit_selectors:
            try:
                submit_btn = page.locator(submit_sel).first
                if await submit_btn.is_visible(timeout=3000):
                    await submit_btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            logger.warning("Could not find submit button for new comment")
            await _safe_screenshot(page, "no_comment_submit.png")
            return False

        await human_delay(2.0, 4.0)
        logger.info("New comment posted: %s...", text[:60])
        return True

    except Exception as e:
        logger.error("Error posting new comment: %s", e)
        await _safe_screenshot(page, "post_error.png")
        return False
