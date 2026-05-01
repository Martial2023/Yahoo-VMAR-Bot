"""Playwright actions — reply to a comment, post a new comment."""

from __future__ import annotations

from playwright.async_api import Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("poster")

# Auteurs à ne jamais répondre (compte officiel VMAR).
SKIP_AUTHORS = {"vision marine", "vision56508"}


def should_skip_author(author: str) -> bool:
    """Return True if the comment author should not receive a reply."""
    lower = author.lower().strip()
    return any(skip in lower for skip in SKIP_AUTHORS)


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

        await human_delay(0.5, 1.0)

        # --- Étape 1 : cliquer sur le bouton "Comment" sous le post ---
        # Yahoo utilise un bouton avec data-testid="comment-action" et la
        # classe "action comment". On essaie plusieurs sélecteurs.
        reply_btn_selectors = [
            '[data-testid="comment-action"]',
            'button.action.comment',
            'button:has(span.comment-label)',
        ]
        clicked = False
        for btn_sel in reply_btn_selectors:
            try:
                btn = comment_el.locator(btn_sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.scroll_into_view_if_needed(timeout=3000)
                    await human_delay(0.3, 0.6)
                    await btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            logger.warning("Could not click reply button for comment %d", comment_index)
            await _safe_screenshot(page, f"no_reply_btn_{comment_index}.png")
            return False

        await human_delay(1.5, 2.5)

        # --- Étape 2 : taper la réponse dans l'éditeur riche ---
        # Le formulaire de réponse a un div contenteditable (éditeur TipTap
        # avec @mention pré-remplie). On tape après la mention.
        reply_input_selectors = [
            'div[contenteditable="true"].community-text-editor',
            'div[contenteditable="true"].tiptap.ProseMirror',
            'div[contenteditable="true"][data-testid="composer-input"]',
            '.editor-wrapper div[contenteditable="true"]',
            'div[contenteditable="true"]',
        ]
        typed = False
        for input_sel in reply_input_selectors:
            try:
                input_el = page.locator(input_sel).last
                if await input_el.is_visible(timeout=5000):
                    await input_el.click()
                    await human_delay(0.3, 0.7)
                    # Aller à la fin du contenu (après la @mention pré-remplie)
                    await page.keyboard.press("End")
                    await human_delay(0.2, 0.4)
                    # Ajouter un espace après la mention puis taper le texte
                    await input_el.press_sequentially(f" {reply_text}", delay=80)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not find reply input field for comment %d", comment_index)
            await _safe_screenshot(page, f"no_reply_input_{comment_index}.png")
            return False

        await human_delay(1.0, 2.0)

        # --- Étape 3 : cliquer "Comment" (data-testid="compose-save") ---
        try:
            submit_btn = page.locator('[data-testid="compose-save"]').first
            await submit_btn.scroll_into_view_if_needed(timeout=3000)
            await human_delay(0.3, 0.6)
            await submit_btn.click(timeout=5000)
        except Exception:
            # Fallback
            fallbacks = [
                'button.primary-btn:has-text("Comment")',
                'button:has-text("Comment"):not([data-testid="comment-action"])',
            ]
            submitted = False
            for sel in fallbacks:
                try:
                    fb = page.locator(sel).first
                    if await fb.is_visible(timeout=3000):
                        await fb.click()
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

        # --- Étape 1 : cliquer sur le placeholder "What's on your mind?" ---
        try:
            expand_btn = page.locator('[data-testid="post-composer-expand-button"]').first
            await expand_btn.click(timeout=5000)
        except Exception:
            logger.warning("Could not find/click post composer expand button")
            await _safe_screenshot(page, "no_comment_input.png")
            return False

        await human_delay(1.0, 2.0)

        # --- Étape 2 : taper le texte dans l'éditeur riche ---
        editor_selectors = [
            'div[contenteditable="true"][data-testid="composer-input"]',
            'div[contenteditable="true"].composer-input',
            'div[contenteditable="true"]',
        ]
        typed = False
        for input_sel in editor_selectors:
            try:
                input_el = page.locator(input_sel).last
                if await input_el.is_visible(timeout=5000):
                    await input_el.click()
                    await human_delay(0.3, 0.7)
                    await input_el.press_sequentially(text, delay=80)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.warning("Could not find post editor after expanding")
            await _safe_screenshot(page, "no_post_editor.png")
            return False

        await human_delay(1.5, 3.0)

        # --- Étape 3 : cliquer "Post" (data-testid="post-composer-footer-send") ---
        try:
            submit_btn = page.locator('[data-testid="post-composer-footer-send"]').first
            await submit_btn.click(timeout=5000)
        except Exception:
            # Fallback
            fallbacks = [
                'button.primary-btn:has-text("Post")',
                'button:has-text("Post")',
            ]
            submitted = False
            for sel in fallbacks:
                try:
                    fb = page.locator(sel).first
                    if await fb.is_visible(timeout=3000):
                        await fb.click()
                        submitted = True
                        break
                except Exception:
                    continue
            if not submitted:
                logger.warning("Could not find submit button for new post")
                await _safe_screenshot(page, "no_comment_submit.png")
                return False

        await human_delay(2.0, 4.0)
        logger.info("New comment posted: %s...", text[:60])
        return True

    except Exception as e:
        logger.error("Error posting new comment: %s", e)
        await _safe_screenshot(page, "post_error.png")
        return False
