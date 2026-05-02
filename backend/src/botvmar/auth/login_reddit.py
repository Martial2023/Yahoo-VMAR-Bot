"""Automated Reddit login via Firefox + IMAP magic link.

Reddit blocks Playwright's bundled Chromium at login (fingerprinting).
Firefox is used instead — it has no App-Bound cookie encryption and is
not flagged by Reddit's anti-bot system.

The flow uses Reddit's "email me a link" (magic link) authentication
rather than username/password, since Reddit password login is increasingly
restricted and magic link is more reliable for automation.
"""

from __future__ import annotations

import asyncio
import json
import time

from playwright.async_api import async_playwright

from botvmar.auth.imap_reader import ImapConfig, extract_magic_link, get_body, poll_for_email
from botvmar.browser.session import _session_path_for
from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("auth.reddit")

_PLATFORM_KEY = "reddit"


async def _safe_screenshot(page, name: str) -> None:
    try:
        await page.screenshot(path=str(SCREENSHOTS_DIR / name), timeout=10000)
    except Exception:
        pass


async def auto_login_reddit(
    credentials: dict,
    imap_cfg: ImapConfig,
) -> bool:
    """Fully automated Reddit login using magic link + IMAP.

    Parameters
    ----------
    credentials : dict
        Must contain ``email`` (the Reddit account email).
        ``password`` is optional (not used for magic link flow).
    imap_cfg : ImapConfig
        IMAP connection for reading the magic link email.
    """
    email_addr = credentials.get("email", "")
    if not email_addr:
        logger.error("[reddit] credentials missing email")
        return False

    logger.info("[reddit] starting auto-login for %s", email_addr)
    pw = await async_playwright().start()
    browser = None

    try:
        # MUST use Firefox — Chrome is blocked by Reddit
        browser = await pw.firefox.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        page = await context.new_page()

        # Step 1: Navigate to Reddit login
        try:
            await page.goto(
                "https://www.reddit.com/login/",
                wait_until="domcontentloaded",
                timeout=120_000,
            )
        except Exception as e:
            logger.warning("[reddit] login page load failed: %s — trying homepage", e)
            await page.goto(
                "https://www.reddit.com/",
                wait_until="domcontentloaded",
                timeout=120_000,
            )

        await human_delay(2.0, 4.0)
        await _safe_screenshot(page, "reddit_login_page.png")

        # Step 2: Switch to email / magic link flow
        # Reddit's login page may default to username+password.
        # Look for "Continue with email" / "Log in" / email input.
        # Try clicking the email/magic-link tab/button first.
        email_tab_selectors = [
            'button:has-text("Continue with email")',
            'a:has-text("Continue with email")',
            'button:has-text("Email")',
            'a:has-text("Email me a link")',
            'button:has-text("Email me a link")',
        ]
        for sel in email_tab_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    await human_delay(1.5, 3.0)
                    break
            except Exception:
                continue

        await _safe_screenshot(page, "reddit_email_tab.png")

        # Step 3: Enter the email address
        email_input_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[name="username"]',
            '#loginUsername',
            'input[placeholder*="email"]',
            'input[placeholder*="Email"]',
        ]
        typed = False
        for sel in email_input_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=5000):
                    await loc.click()
                    await human_delay(0.3, 0.5)
                    await loc.fill(email_addr)
                    typed = True
                    break
            except Exception:
                continue

        if not typed:
            logger.error("[reddit] could not find email input")
            await _safe_screenshot(page, "reddit_no_email_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Step 4: Submit to request magic link
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Continue")',
            'button:has-text("Send")',
            'button:has-text("Email me")',
            'button:has-text("Log In")',
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await btn.click()
                    break
            except Exception:
                continue

        await human_delay(3.0, 5.0)
        await _safe_screenshot(page, "reddit_after_submit.png")

        # Step 5: Poll IMAP for the magic link email
        logger.info("[reddit] magic link requested — polling IMAP...")
        before_ts = time.time() - 30

        msg = await asyncio.to_thread(
            poll_for_email,
            imap_cfg,
            sender_filter="reddit",
            subject_contains="sign in",
            since_timestamp=before_ts,
            timeout_seconds=120,
        )
        if msg is None:
            # Try alternative subject patterns
            for alt_subject in ["log in", "magic link", "verify"]:
                msg = await asyncio.to_thread(
                    poll_for_email,
                    imap_cfg,
                    sender_filter="reddit",
                    subject_contains=alt_subject,
                    since_timestamp=before_ts,
                    timeout_seconds=20,
                )
                if msg:
                    break

        if msg is None:
            logger.error("[reddit] magic link email not received within timeout")
            await _safe_screenshot(page, "reddit_magic_link_timeout.png")
            return False

        body = get_body(msg)
        link = extract_magic_link(body, domain="reddit.com")
        if not link:
            logger.error("[reddit] could not extract magic link from email body")
            logger.debug("[reddit] email body preview: %s", body[:500])
            return False

        logger.info("[reddit] magic link found — navigating...")

        # Step 6: Navigate to the magic link
        await page.goto(link, wait_until="domcontentloaded", timeout=60000)
        await human_delay(5.0, 8.0)
        await _safe_screenshot(page, "reddit_after_magic_link.png")

        # Step 7: Verify login success
        url = page.url
        if "/login" in url or "/register" in url:
            logger.error("[reddit] login failed — still on login page: %s", url)
            await _safe_screenshot(page, "reddit_login_failed.png")
            return False

        # Step 8: Save session
        # Reddit sessions captured in Firefox can be injected into Chromium
        # (same approach as scripts/login_reddit.py)
        session_path = _session_path_for(_PLATFORM_KEY)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        session_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

        reddit_cookies = [
            c for c in state.get("cookies", [])
            if "reddit" in c.get("domain", "")
        ]
        logger.info(
            "[reddit] auto-login successful — %d Reddit cookies saved to %s",
            len(reddit_cookies), session_path,
        )
        return len(reddit_cookies) > 0

    except Exception as e:
        logger.error("[reddit] auto-login failed: %s", e, exc_info=True)
        return False
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        await pw.stop()
