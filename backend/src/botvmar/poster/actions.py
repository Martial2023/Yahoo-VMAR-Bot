"""Playwright actions — reply to a comment, post a new comment."""

from __future__ import annotations

from playwright.async_api import Page

from botvmar.browser.stealth import human_click, human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("poster")


async def reply_to_comment(
    page: Page,
    comment_selector: str,
    comment_index: int,
    reply_text: str,
) -> bool:
    """Click reply on a specific comment, type, submit. Returns success."""
    try:
        comment_el = page.locator(comment_selector).nth(comment_index)

        # SELECTOR (Yahoo 2026): le bouton "Comment" sous chaque post ouvre la
        # zone de réponse. L'ancien "Reply" n'existe plus.
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
                    await human_click(page, f"{comment_selector}:nth-child({comment_index + 1}) {btn_sel}")
                    clicked = True
                    break
            except Exception:
                try:
                    await btn.click()
                    clicked = True
                    break
                except Exception:
                    continue

        if not clicked:
            logger.warning("Could not find reply button for comment %d", comment_index)
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"no_reply_btn_{comment_index}.png"))
            return False

        await human_delay(1.0, 2.0)

        # SELECTOR: reply text input
        reply_input_selectors = [
            '[data-testid="reply-input"]',
            'textarea[placeholder*="reply"]',
            'textarea[placeholder*="Reply"]',
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
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"no_reply_input_{comment_index}.png"))
            return False

        await human_delay(1.0, 2.0)

        # SELECTOR: submit reply button
        submit_selectors = [
            'button:has-text("Post")',
            'button:has-text("Submit")',
            '[data-testid="submit-reply"]',
            'button[type="submit"]',
            'button[class*="submit"]',
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
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"no_submit_btn_{comment_index}.png"))
            return False

        await human_delay(2.0, 4.0)
        logger.info("Reply posted to comment %d: %s...", comment_index, reply_text[:60])
        return True

    except Exception as e:
        logger.error("Error replying to comment %d: %s", comment_index, e)
        try:
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"reply_error_{comment_index}.png"))
        except Exception:
            pass
        return False


async def post_new_comment(page: Page, ticker: str, text: str) -> bool:
    """Post a brand-new comment on the community page."""
    try:
        if "community" not in page.url.lower():
            await page.goto(
                f"https://ca.finance.yahoo.com/quote/{ticker}/community",
                wait_until="commit",
                timeout=120000,
            )
            await human_delay(4.0, 6.0)

        # SELECTOR: main comment input
        comment_input_selectors = [
            '[data-testid="comment-input"]',
            'textarea[placeholder*="comment"]',
            'textarea[placeholder*="Comment"]',
            'textarea[placeholder*="Share your thoughts"]',
            'div[data-placeholder*="comment"]',
            'div[contenteditable="true"]',
            '.comment-input textarea',
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
            await page.screenshot(path=str(SCREENSHOTS_DIR / "no_comment_input.png"))
            return False

        await human_delay(1.5, 3.0)

        # SELECTOR: submit button
        submit_selectors = [
            'button:has-text("Post")',
            'button:has-text("Comment")',
            'button:has-text("Submit")',
            '[data-testid="submit-comment"]',
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
            logger.warning("Could not find submit button for new comment")
            await page.screenshot(path=str(SCREENSHOTS_DIR / "no_comment_submit.png"))
            return False

        await human_delay(2.0, 4.0)
        logger.info("New comment posted: %s...", text[:60])
        return True

    except Exception as e:
        logger.error("Error posting new comment: %s", e)
        try:
            await page.screenshot(path=str(SCREENSHOTS_DIR / "post_error.png"))
        except Exception:
            pass
        return False
