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

        # Step 2: Enter email in #username
        email_sel = "#username"
        try:
            loc = page.locator(email_sel).first
            if not await loc.is_visible(timeout=8000):
                raise Exception("not visible")
            await human_type(page, email_sel, email_addr)
        except Exception:
            logger.error("[yahoo] could not find email input (#username)")
            await _safe_screenshot(page, "yahoo_no_email_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Step 3: Click "Next" button (name="signin")
        signin_sel = 'button[name="signin"]'
        try:
            await human_click(page, signin_sel)
        except Exception:
            logger.error("[yahoo] could not click signin/next button")
            await _safe_screenshot(page, "yahoo_no_signin_btn.png")
            return False

        await human_delay(3.0, 5.0)
        await _safe_screenshot(page, "yahoo_after_email.png")

        # Step 4: Enter password in #login-passwd
        passwd_sel = "#login-passwd"
        try:
            loc = page.locator(passwd_sel).first
            if not await loc.is_visible(timeout=10000):
                raise Exception("not visible")
            await human_type(page, passwd_sel, password)
        except Exception:
            logger.error("[yahoo] could not find password input (#login-passwd)")
            await _safe_screenshot(page, "yahoo_no_passwd_input.png")
            return False

        await human_delay(0.5, 1.0)

        # Step 5: Click "Next" button (name="validate") to submit password
        validate_sel = 'button[name="validate"]'
        try:
            await human_click(page, validate_sel)
        except Exception:
            logger.error("[yahoo] could not click validate/next button after password")
            await _safe_screenshot(page, "yahoo_no_validate_btn.png")
            return False

        await human_delay(3.0, 6.0)
        await _safe_screenshot(page, "yahoo_after_password.png")

        # Step 6: Click the "Send verification code" button (#200)
        # Yahoo shows a challenge page where user must request the code
        send_code_sel = "button#200"
        try:
            loc = page.locator(send_code_sel).first
            if await loc.is_visible(timeout=10000):
                logger.info("[yahoo] verification challenge detected — requesting code")
                await human_click(page, send_code_sel)
                await human_delay(3.0, 5.0)
                await _safe_screenshot(page, "yahoo_after_send_code.png")
            else:
                # No challenge page — maybe already logged in or different flow
                logger.info("[yahoo] no verification challenge button found, checking state...")
        except Exception:
            logger.info("[yahoo] no #200 button — skipping send-code step")

        # Step 7: Fill OTP digits one by one (#verify-code-0 through #verify-code-5)
        otp_first_sel = "#verify-code-0"
        try:
            loc = page.locator(otp_first_sel).first
            otp_needed = await loc.is_visible(timeout=10000)
        except Exception:
            otp_needed = False

        if otp_needed:
            logger.info("[yahoo] OTP input detected — polling IMAP for verification code...")
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

            # Type each digit into its respective input field
            for i, digit in enumerate(code[:6]):
                digit_sel = f"#verify-code-{i}"
                try:
                    await page.locator(digit_sel).first.fill(digit)
                    await human_delay(0.1, 0.3)
                except Exception as e:
                    logger.error("[yahoo] failed to fill digit %d: %s", i, e)
                    return False

            await human_delay(0.5, 1.0)

            # Step 8: Click "Next" to submit the OTP (name="validate")
            try:
                await human_click(page, validate_sel)
            except Exception:
                # Try generic submit as fallback
                try:
                    await human_click(page, 'button[type="submit"]')
                except Exception:
                    logger.error("[yahoo] could not submit OTP")
                    return False

            await human_delay(5.0, 8.0)
            await _safe_screenshot(page, "yahoo_after_otp.png")

        # Step 9: Verify login success
        current_url = page.url
        if "login.yahoo.com" in current_url:
            logger.error("[yahoo] login failed — still on login page: %s", current_url)
            await _safe_screenshot(page, "yahoo_login_failed.png")
            return False

        # Step 10: Save session
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
