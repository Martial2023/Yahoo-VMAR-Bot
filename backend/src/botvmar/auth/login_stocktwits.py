"""Automated StockTwits login via Playwright + IMAP OTP verification."""

from __future__ import annotations

import asyncio
import json
import time

from playwright.async_api import async_playwright

from botvmar.auth.imap_reader import ImapConfig, extract_otp, get_body, poll_for_email
from botvmar.browser.session import _session_path_for
from botvmar.browser.stealth import apply_stealth, get_random_user_agent, human_click, human_delay, human_type
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.utils.logger import get_logger

logger = get_logger("auth.stocktwits")

_PLATFORM_KEY = "stocktwits"


async def _safe_screenshot(page, name: str) -> None:
    try:
        await page.screenshot(path=str(SCREENSHOTS_DIR / name), timeout=10000)
    except Exception:
        pass


async def auto_login_stocktwits(
    credentials: dict,
    imap_cfg: ImapConfig,
) -> bool:
    """Fully automated StockTwits login with IMAP-based OTP verification.

    Parameters
    ----------
    credentials : dict
        Must contain ``email`` and ``password``.
    imap_cfg : ImapConfig
        IMAP connection for reading the OTP email.
    """
    email_addr = credentials.get("email", "")
    password = credentials.get("password", "")
    if not email_addr or not password:
        logger.error("[stocktwits] credentials missing email or password")
        return False

    logger.info("[stocktwits] starting auto-login for %s", email_addr)
    pw = await async_playwright().start()
    browser = None

    try:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=get_random_user_agent(),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await apply_stealth(context)
        page = await context.new_page()

        # Step 1: Navigate to StockTwits sign-in
        # Cloudflare protection requires lenient wait + long timeout
        try:
            await page.goto(
                "https://stocktwits.com/signin",
                wait_until="commit",
                timeout=120_000,
            )
        except Exception as e:
            logger.warning("[stocktwits] signin page load failed (%s), trying homepage", e)
            await page.goto(
                "https://stocktwits.com/",
                wait_until="commit",
                timeout=120_000,
            )

        await human_delay(3.0, 5.0)
        await _safe_screenshot(page, "stocktwits_login_page.png")

        # Step 2: Fill email
        email_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="Email"]',
            'input[placeholder*="email"]',
        ]
        typed_email = False
        for sel in email_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=5000):
                    await human_type(page, sel, email_addr)
                    typed_email = True
                    break
            except Exception:
                continue

        if not typed_email:
            logger.error("[stocktwits] could not find email input")
            await _safe_screenshot(page, "stocktwits_no_email_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Step 3: Fill password
        pw_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[placeholder*="Password"]',
            'input[placeholder*="password"]',
        ]
        typed_pw = False
        for sel in pw_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=5000):
                    await human_type(page, sel, password)
                    typed_pw = True
                    break
            except Exception:
                continue

        if not typed_pw:
            logger.error("[stocktwits] could not find password input")
            await _safe_screenshot(page, "stocktwits_no_pw_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Step 4: Click Sign In
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Log In")',
            'input[type="submit"]',
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=3000):
                    await human_click(page, sel)
                    break
            except Exception:
                continue

        await human_delay(3.0, 6.0)
        await _safe_screenshot(page, "stocktwits_after_submit.png")

        # Step 5: Check if OTP verification is required
        otp_selectors = [
            'input[name="code"]',
            'input[name="verify_code"]',
            'input[name="verification_code"]',
            'input[placeholder*="code"]',
            'input[placeholder*="Code"]',
            'input[type="tel"]',
        ]

        otp_needed = False
        otp_sel_found = ""
        for sel in otp_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=10000):
                    otp_needed = True
                    otp_sel_found = sel
                    break
            except Exception:
                continue

        if otp_needed:
            logger.info("[stocktwits] OTP verification required — polling IMAP...")
            before_ts = time.time() - 30

            msg = await asyncio.to_thread(
                poll_for_email,
                imap_cfg,
                sender_filter="stocktwits",
                subject_contains="verification",
                since_timestamp=before_ts,
                timeout_seconds=120,
            )
            if msg is None:
                # Try alternative subject
                msg = await asyncio.to_thread(
                    poll_for_email,
                    imap_cfg,
                    sender_filter="stocktwits",
                    subject_contains="code",
                    since_timestamp=before_ts,
                    timeout_seconds=30,
                )
            if msg is None:
                logger.error("[stocktwits] OTP email not received within timeout")
                await _safe_screenshot(page, "stocktwits_otp_timeout.png")
                return False

            body = get_body(msg)
            code = extract_otp(body)
            if not code:
                logger.error("[stocktwits] could not extract OTP from email body")
                return False

            logger.info("[stocktwits] OTP extracted: %s", code)

            await human_type(page, otp_sel_found, code)
            await human_delay(0.5, 1.0)

            # Submit OTP
            for sel in submit_selectors + ['button:has-text("Verify")', 'button:has-text("Confirm")']:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await human_click(page, sel)
                        break
                except Exception:
                    continue

            await human_delay(5.0, 8.0)
            await _safe_screenshot(page, "stocktwits_after_otp.png")

        # Step 6: Verify login success
        current_url = page.url
        if "/signin" in current_url or "/signup" in current_url:
            logger.error("[stocktwits] login failed — still on login page: %s", current_url)
            await _safe_screenshot(page, "stocktwits_login_failed.png")
            return False

        # Step 7: Save session
        session_path = _session_path_for(_PLATFORM_KEY)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        session_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        logger.info("[stocktwits] auto-login successful — session saved to %s", session_path)
        return True

    except Exception as e:
        logger.error("[stocktwits] auto-login failed: %s", e, exc_info=True)
        return False
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        await pw.stop()
