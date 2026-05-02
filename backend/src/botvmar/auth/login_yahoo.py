"""Automated Yahoo Finance login via Playwright + IMAP OTP verification."""

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

logger = get_logger("auth.yahoo")

# Session key matching browser/session.py convention
_PLATFORM_KEY = "yahoo_finance"


async def _safe_screenshot(page, name: str) -> None:
    try:
        await page.screenshot(path=str(SCREENSHOTS_DIR / name), timeout=10000)
    except Exception:
        pass


async def auto_login_yahoo(
    credentials: dict,
    imap_cfg: ImapConfig,
) -> bool:
    """Fully automated Yahoo login with IMAP-based OTP verification.

    Parameters
    ----------
    credentials : dict
        Must contain ``email`` and ``password``.
    imap_cfg : ImapConfig
        IMAP connection for reading the OTP email.

    Returns True on success, False on any failure.
    """
    email_addr = credentials.get("email", "")
    password = credentials.get("password", "")
    if not email_addr or not password:
        logger.error("[yahoo] credentials missing email or password")
        return False

    logger.info("[yahoo] starting auto-login for %s", email_addr)
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

        # Step 1: Navigate to Yahoo login
        await page.goto("https://login.yahoo.com", wait_until="domcontentloaded", timeout=60000)
        await human_delay(2.0, 4.0)
        await _safe_screenshot(page, "yahoo_login_page.png")

        # Step 2: Enter email
        email_selectors = ["#login-username", 'input[name="username"]']
        typed = False
        for sel in email_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=5000):
                    await human_type(page, sel, email_addr)
                    typed = True
                    break
            except Exception:
                continue
        if not typed:
            logger.error("[yahoo] could not find email input")
            await _safe_screenshot(page, "yahoo_no_email_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Click Next/Sign in
        next_selectors = ["#login-signin", 'button[name="signin"]', 'input[type="submit"]']
        for sel in next_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=3000):
                    await human_click(page, sel)
                    break
            except Exception:
                continue

        await human_delay(3.0, 5.0)
        await _safe_screenshot(page, "yahoo_after_email.png")

        # Step 3: Enter password (if password page appears)
        pw_selectors = ["#login-passwd", 'input[name="password"]', 'input[type="password"]']
        for sel in pw_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.is_visible(timeout=8000):
                    await human_type(page, sel, password)
                    await human_delay(0.5, 1.0)
                    # Click sign in
                    for btn_sel in next_selectors:
                        try:
                            btn = page.locator(btn_sel).first
                            if await btn.is_visible(timeout=3000):
                                await human_click(page, btn_sel)
                                break
                        except Exception:
                            continue
                    break
            except Exception:
                continue

        await human_delay(3.0, 6.0)
        await _safe_screenshot(page, "yahoo_after_password.png")

        # Step 4: Check if OTP / verification code is required
        otp_selectors = [
            'input[name="verify_code"]',
            'input[name="code"]',
            "#verification-code-field",
            'input[data-test-id="verify-code-input"]',
            'input[type="tel"]',  # Yahoo sometimes uses tel for OTP
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
            logger.info("[yahoo] OTP verification required — polling IMAP...")
            before_ts = time.time() - 30

            msg = await asyncio.to_thread(
                poll_for_email,
                imap_cfg,
                sender_filter="yahoo",
                subject_contains="verification",
                since_timestamp=before_ts,
                timeout_seconds=120,
            )
            if not msg:
                logger.error("[yahoo] OTP email not received within timeout")
                await _safe_screenshot(page, "yahoo_otp_timeout.png")
                return False

            body = get_body(msg)
            code = extract_otp(body)
            if not code:
                logger.error("[yahoo] could not extract OTP from email body")
                return False

            logger.info("[yahoo] OTP extracted: %s", code)

            # Type the OTP
            await human_type(page, otp_sel_found, code)
            await human_delay(0.5, 1.0)

            # Submit
            submit_selectors = [
                'button[type="submit"]',
                "#verify-code-button",
                'button:has-text("Verify")',
                'button:has-text("Submit")',
            ]
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=3000):
                        await human_click(page, sel)
                        break
                except Exception:
                    continue

            await human_delay(5.0, 8.0)
            await _safe_screenshot(page, "yahoo_after_otp.png")

        # Step 5: Verify login success
        current_url = page.url
        if "login.yahoo.com" in current_url:
            logger.error("[yahoo] login failed — still on login page: %s", current_url)
            await _safe_screenshot(page, "yahoo_login_failed.png")
            return False

        # Step 6: Save session
        session_path = _session_path_for(_PLATFORM_KEY)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        session_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        logger.info("[yahoo] auto-login successful — session saved to %s", session_path)
        return True

    except Exception as e:
        logger.error("[yahoo] auto-login failed: %s", e, exc_info=True)
        return False
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        await pw.stop()
