"""Playwright actions for StockTwits — reply to a message, post a new message."""

from __future__ import annotations

from playwright.async_api import Locator, Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("poster.stocktwits")

# Type the first N characters one-by-one (looks human), inject the rest instantly.
_CHAR_TYPING_LIMIT = 40


async def _safe_screenshot(page: Page, name: str) -> None:
    """Take a screenshot, silently ignoring errors."""
    try:
        await page.screenshot(
            path=str(SCREENSHOTS_DIR / name),
            timeout=10000,
        )
    except Exception:
        pass


async def _type_text(page: Page, editor: Locator, text: str) -> None:
    """Type *text* into a DraftEditor, inserting the tail via execCommand.

    DraftEditor doesn't support Playwright's ``fill()``.
    ``press_sequentially`` at 80 ms/char is too slow for long texts (timeout).
    Strategy: type a short head character-by-character (looks human), then
    inject the remainder via ``document.execCommand('insertText')`` which
    works in any ``contenteditable`` without clipboard permissions.
    """
    if len(text) <= _CHAR_TYPING_LIMIT:
        await editor.press_sequentially(text, delay=80)
        return
    head, tail = text[:_CHAR_TYPING_LIMIT], text[_CHAR_TYPING_LIMIT:]
    await editor.press_sequentially(head, delay=80)
    await human_delay(0.3, 0.5)
    # Focus the editor and inject the rest via execCommand (no clipboard needed)
    await editor.focus()
    await page.evaluate("text => document.execCommand('insertText', false, text)", tail)
    await human_delay(0.5, 1.0)


async def reply_to_message(
    page: Page,
    message_selector: str,
    message_index: int,
    reply_text: str,
) -> bool:
    """Click reply on a StockTwits message, type reply, submit. Returns success."""
    try:
        msg_el = page.locator(message_selector).nth(message_index)

        # Scroll the message into view
        try:
            await msg_el.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            logger.warning("Message %d not visible/accessible", message_index)
            return False

        await human_delay(0.5, 1.0)

        # --- Step 1: Click the Reply button (aria-label="Reply") ---
        reply_btn_selectors = [
            'button[aria-label="Reply"]',
            '[class*="StreamMessageItem_activeContainer"] >> nth=0',
        ]
        clicked = False
        for btn_sel in reply_btn_selectors:
            try:
                btn = msg_el.locator(btn_sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.6)
                    await btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            logger.warning(
                "Could not click reply button for message %d", message_index,
            )
            await _safe_screenshot(page, f"st_no_reply_btn_{message_index}.png")
            return False

        await human_delay(1.0, 1.5)

        # --- Step 2: Type reply in the Draft.js rich-text editor ---
        # A popup / inline form appears with a Draft.js editor pre-filled
        # with @AuthorName. We type after the mention.

        # First, wait for the reply modal editor to appear (it contains a
        # "Write your reply" placeholder and is inside a modal container).
        reply_modal_selectors = [
            '[class*="InputPost_insideModalContainer"] div[contenteditable="true"]',
            '[class*="Default_textarea"] div[contenteditable="true"].public-DraftEditor-content',
        ]
        editor = None
        for modal_sel in reply_modal_selectors:
            try:
                await page.wait_for_selector(modal_sel, state="visible", timeout=8000)
                editor = page.locator(modal_sel).last
                break
            except Exception:
                continue

        # Fallback: try generic selectors if the modal-specific ones fail
        if editor is None:
            generic_selectors = [
                'div[contenteditable="true"].public-DraftEditor-content',
                '.DraftEditor-root div[contenteditable="true"]',
                'div[contenteditable="true"]',
            ]
            for ed_sel in generic_selectors:
                try:
                    loc = page.locator(ed_sel).last
                    if await loc.is_visible(timeout=3000):
                        editor = loc
                        break
                except Exception:
                    continue

        if editor is None:
            logger.warning(
                "Could not find reply editor for message %d", message_index,
            )
            await _safe_screenshot(page, f"st_no_reply_editor_{message_index}.png")
            return False

        typed = False
        try:
            await editor.click()
            await human_delay(0.3, 0.7)
            await page.keyboard.press("End")
            await human_delay(0.2, 0.4)

            await _type_text(page, editor, f" {reply_text}")

            typed = True
        except Exception as e:
            logger.warning("Failed to type in reply editor: %s", e)

        if not typed:
            logger.warning(
                "Could not type in reply editor for message %d", message_index,
            )
            await _safe_screenshot(page, f"st_no_reply_editor_{message_index}.png")
            return False

        await human_delay(1.0, 2.0)

        # --- Step 3: Click the "Reply" submit button ---
        submit_selectors = [
            'button[class*="STButton_black-primary"]:has(span:text("Reply"))',
            'button:has(span[class*="ButtonPost_text"]:text("Reply"))',
            'button[type="button"]:has-text("Reply"):not([aria-label="Reply"])',
        ]
        submitted = False
        for sub_sel in submit_selectors:
            try:
                sub_btn = page.locator(sub_sel).first
                if await sub_btn.is_visible(timeout=3000):
                    await sub_btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.6)
                    await sub_btn.click(timeout=5000)
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            logger.warning("Could not find submit button for reply")
            await _safe_screenshot(
                page, f"st_no_submit_btn_{message_index}.png",
            )
            return False

        await human_delay(2.0, 4.0)
        logger.info(
            "Reply posted to StockTwits message %d: %s...",
            message_index, reply_text[:60],
        )
        return True

    except Exception as e:
        logger.error(
            "Error replying to StockTwits message %d: %s", message_index, e,
        )
        await _safe_screenshot(page, f"st_reply_error_{message_index}.png")
        return False


async def post_new_message(page: Page, ticker: str, text: str) -> bool:
    """Post a brand-new message on the StockTwits symbol stream."""
    try:
        # Navigate to the symbol page if not already there
        if "stocktwits.com" not in page.url or ticker.upper() not in page.url.upper():
            url = f"https://stocktwits.com/symbol/{ticker}"
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await human_delay(4.0, 6.0)

        # --- Step 1: Click the compose area / "What are you thinking?" ---
        compose_selectors = [
            '[data-testid="compose-input"]',
            'div[contenteditable="true"].public-DraftEditor-content',
            'div[contenteditable="true"][role="textbox"]',
            '[class*="ComposeForm"] div[contenteditable="true"]',
            'div[contenteditable="true"]',
        ]
        editor_found = False
        for comp_sel in compose_selectors:
            try:
                el = page.locator(comp_sel).first
                if await el.is_visible(timeout=5000):
                    await el.click()
                    await human_delay(0.5, 1.0)
                    editor_found = True
                    break
            except Exception:
                continue

        if not editor_found:
            logger.warning("Could not find StockTwits compose area")
            await _safe_screenshot(page, "st_no_compose.png")
            return False

        await human_delay(1.0, 2.0)

        # --- Step 2: Type the message ---
        # After clicking, the editor should be active. Re-locate to be safe.
        typed = False
        for comp_sel in compose_selectors:
            try:
                editor = page.locator(comp_sel).first
                if await editor.is_visible(timeout=3000):
                    await editor.click()
                    await human_delay(0.3, 0.5)
                    await _type_text(page, editor, text)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not type in StockTwits compose editor")
            await _safe_screenshot(page, "st_no_compose_editor.png")
            return False

        await human_delay(1.5, 3.0)

        # --- Step 3: Click "Post" submit button ---
        post_selectors = [
            'button[class*="STButton_black-primary"]:has(span:text("Post"))',
            'button:has(span[class*="ButtonPost_text"]:text("Post"))',
            'button[type="button"]:has-text("Post")',
        ]
        posted = False
        for p_sel in post_selectors:
            try:
                btn = page.locator(p_sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.6)
                    await btn.click(timeout=5000)
                    posted = True
                    break
            except Exception:
                continue

        if not posted:
            logger.warning("Could not find StockTwits post submit button")
            await _safe_screenshot(page, "st_no_post_submit.png")
            return False

        await human_delay(2.0, 4.0)
        logger.info("New message posted on StockTwits: %s...", text[:60])
        return True

    except Exception as e:
        logger.error("Error posting new StockTwits message: %s", e)
        await _safe_screenshot(page, "st_post_error.png")
        return False
