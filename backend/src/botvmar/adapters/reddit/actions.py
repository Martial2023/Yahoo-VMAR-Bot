"""Playwright actions for Reddit — reply to a comment or comment on a post."""

from __future__ import annotations

from playwright.async_api import Locator, Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("poster.reddit")

# Type first N chars one-by-one (human-like), inject the rest instantly.
_CHAR_TYPING_LIMIT = 40


async def _safe_screenshot(page: Page, name: str) -> None:
    try:
        await page.screenshot(path=str(SCREENSHOTS_DIR / name), timeout=10000)
    except Exception:
        pass


async def _type_text(page: Page, editor: Locator, text: str) -> None:
    """Type *text* into a Lexical contenteditable editor.

    Types a short head character-by-character (looks human), then injects the
    rest via ``document.execCommand('insertText')`` to avoid Playwright timeout.
    """
    if len(text) <= _CHAR_TYPING_LIMIT:
        await editor.press_sequentially(text, delay=80)
        return
    head, tail = text[:_CHAR_TYPING_LIMIT], text[_CHAR_TYPING_LIMIT:]
    await editor.press_sequentially(head, delay=80)
    await human_delay(0.3, 0.5)
    await editor.focus()
    await page.evaluate(
        "text => document.execCommand('insertText', false, text)", tail,
    )
    await human_delay(0.5, 1.0)


async def reply_to_comment(
    page: Page,
    comment_selector: str,
    comment_index: int,
    reply_text: str,
) -> bool:
    """Click reply on a Reddit comment, type reply, submit. Returns success."""
    try:
        comment_el = page.locator(comment_selector).nth(comment_index)

        # Scroll the comment into view
        try:
            await comment_el.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            logger.warning("Reddit comment %d not visible/accessible", comment_index)
            return False

        await human_delay(0.5, 1.5)

        # --- Step 1: Click the Reply button ---
        # Reddit uses a button with name="comments-action-button" or
        # a reply button with specific aria-label / data attributes.
        reply_btn_selectors = [
            'button[name="comments-action-button"]',
            'button[data-post-click-location="comments-button"]',
            'button:has(svg[icon-name="comment"])',
        ]
        clicked = False
        for btn_sel in reply_btn_selectors:
            try:
                btn = comment_el.locator(btn_sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.8)
                    await btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            logger.warning(
                "Could not click reply button for Reddit comment %d",
                comment_index,
            )
            await _safe_screenshot(page, f"reddit_no_reply_btn_{comment_index}.png")
            return False

        await human_delay(1.5, 3.0)

        # --- Step 2: Type reply in the Lexical rich-text editor ---
        # A contenteditable div appears below the comment with
        # data-lexical-editor="true" and role="textbox".
        editor_selectors = [
            'div[data-lexical-editor="true"][contenteditable="true"]',
            'div[slot="rte"][contenteditable="true"]',
            'div[contenteditable="true"][role="textbox"]',
        ]

        # The editor can appear inside the comment element or as a sibling.
        # Try within the comment first, then at page level.
        editor = None
        for ed_sel in editor_selectors:
            try:
                # Within the comment element
                loc = comment_el.locator(ed_sel).first
                if await loc.is_visible(timeout=3000):
                    editor = loc
                    break
            except Exception:
                continue

        if editor is None:
            # Fallback: page-level search (editor might be outside the comment DOM)
            for ed_sel in editor_selectors:
                try:
                    await page.wait_for_selector(ed_sel, state="visible", timeout=5000)
                    loc = page.locator(ed_sel).last
                    if await loc.is_visible(timeout=2000):
                        editor = loc
                        break
                except Exception:
                    continue

        if editor is None:
            logger.warning(
                "Could not find reply editor for Reddit comment %d",
                comment_index,
            )
            await _safe_screenshot(page, f"reddit_no_editor_{comment_index}.png")
            return False

        try:
            await editor.click()
            await human_delay(0.3, 0.7)
            await _type_text(page, editor, reply_text)
        except Exception as e:
            logger.warning("Failed to type in Reddit reply editor: %s", e)
            await _safe_screenshot(page, f"reddit_type_error_{comment_index}.png")
            return False

        await human_delay(1.0, 2.0)

        # --- Step 3: Click the submit button ---
        submit_selectors = [
            'button#comment-composer-submit-button',
            'button[slot="submit-button"][type="submit"]',
            'button[type="submit"]:has-text("Comment")',
            'button[type="submit"]:has-text("Commentaire")',
            'button[type="submit"]:has-text("Reply")',
        ]

        # Try within the comment element first, then page-level
        submitted = False
        for sub_sel in submit_selectors:
            try:
                sub_btn = comment_el.locator(sub_sel).first
                if await sub_btn.is_visible(timeout=2000):
                    await sub_btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.6)
                    await sub_btn.click(timeout=5000)
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            # Fallback: page-level
            for sub_sel in submit_selectors:
                try:
                    sub_btn = page.locator(sub_sel).last
                    if await sub_btn.is_visible(timeout=2000):
                        await sub_btn.scroll_into_view_if_needed(timeout=3000)
                        await human_delay(0.3, 0.6)
                        await sub_btn.click(timeout=5000)
                        submitted = True
                        break
                except Exception:
                    continue

        if not submitted:
            logger.warning("Could not find submit button for Reddit reply")
            await _safe_screenshot(page, f"reddit_no_submit_{comment_index}.png")
            return False

        await human_delay(2.0, 4.0)
        logger.info(
            "Reply posted to Reddit comment %d: %s...",
            comment_index, reply_text[:60],
        )
        return True

    except Exception as e:
        logger.error(
            "Error replying to Reddit comment %d: %s", comment_index, e,
        )
        await _safe_screenshot(page, f"reddit_reply_error_{comment_index}.png")
        return False


async def comment_on_post(page: Page, reply_text: str) -> bool:
    """Type a top-level comment on the current Reddit post page and submit.

    Used when a post has zero comments (element_index == -1).
    The main comment box is typically already visible at the bottom of the post.
    """
    try:
        # --- Step 1: Find the main comment editor ---
        # Reddit shows a comment box below the post body.
        # Click on the placeholder first to activate the Lexical editor.
        placeholder_selectors = [
            'shreddit-composer',
            'comment-composer-host',
            'div[data-testid="comment-composer"]',
        ]
        for pl_sel in placeholder_selectors:
            try:
                ph = page.locator(pl_sel).first
                if await ph.is_visible(timeout=3000):
                    await ph.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.8)
                    await ph.click(timeout=3000)
                    await human_delay(1.0, 2.0)
                    break
            except Exception:
                continue

        # Now find the contenteditable Lexical editor
        editor_selectors = [
            'div[data-lexical-editor="true"][contenteditable="true"]',
            'div[slot="rte"][contenteditable="true"]',
            'div[contenteditable="true"][role="textbox"]',
        ]
        editor = None
        for ed_sel in editor_selectors:
            try:
                await page.wait_for_selector(ed_sel, state="visible", timeout=8000)
                loc = page.locator(ed_sel).first
                if await loc.is_visible(timeout=2000):
                    editor = loc
                    break
            except Exception:
                continue

        if editor is None:
            logger.warning("Could not find comment editor on Reddit post")
            await _safe_screenshot(page, "reddit_no_post_editor.png")
            return False

        await editor.click()
        await human_delay(0.3, 0.7)
        await _type_text(page, editor, reply_text)
        await human_delay(1.0, 2.0)

        # --- Step 2: Submit ---
        submit_selectors = [
            'button#comment-composer-submit-button',
            'button[slot="submit-button"][type="submit"]',
            'button[type="submit"]:has-text("Comment")',
            'button[type="submit"]:has-text("Commentaire")',
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
            logger.warning("Could not find submit button for Reddit post comment")
            await _safe_screenshot(page, "reddit_no_post_submit.png")
            return False

        await human_delay(2.0, 4.0)
        logger.info("Comment posted on Reddit post: %s...", reply_text[:60])
        return True

    except Exception as e:
        logger.error("Error commenting on Reddit post: %s", e)
        await _safe_screenshot(page, "reddit_post_comment_error.png")
        return False
