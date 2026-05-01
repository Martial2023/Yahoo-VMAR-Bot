"""Browser session — launch browser, save/restore storage state, validate.

Supports multiple platforms via `create_browser_for(platform_key)`.  Each
platform stores its cookies in `sessions/<key>_session.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from botvmar.browser.stealth import apply_stealth, get_random_user_agent, human_delay
from botvmar.config.env import PROJECT_ROOT, PROXY_URL, SCREENSHOTS_DIR, SESSION_FILE, SESSIONS_DIR
from botvmar.utils.logger import get_logger
from botvmar.utils.notifier import notify

logger = get_logger("session")


def _session_path() -> Path:
    return PROJECT_ROOT / SESSION_FILE


def _session_path_for(platform_key: str) -> Path:
    """Return the session file path for a given platform key."""
    return SESSIONS_DIR / f"{platform_key}_session.json"


async def create_browser(headless: bool = True) -> tuple:
    """Launch Chromium with stealth + saved storage state if any."""
    pw = await async_playwright().start()

    launch_args: dict = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    }
    if PROXY_URL:
        launch_args["proxy"] = {"server": PROXY_URL}
        logger.info("Using proxy: %s", PROXY_URL.split("@")[-1] if "@" in PROXY_URL else PROXY_URL)

    browser = await pw.chromium.launch(**launch_args)

    context_args: dict = {
        "user_agent": get_random_user_agent(),
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }
    sp = _session_path()
    if sp.exists():
        context_args["storage_state"] = str(sp)
        logger.info("Loading saved session from %s", sp)
    else:
        logger.warning("No saved session found — bot will not be logged in")

    context = await browser.new_context(**context_args)
    await apply_stealth(context)
    page = await context.new_page()
    return pw, browser, context, page


async def create_browser_for(
    platform_key: str,
    *,
    headless: bool = True,
) -> tuple:
    """Launch Chromium with stealth + saved session for `platform_key`.

    Session file: ``sessions/{platform_key}_session.json``.
    Falls back to `create_browser` semantics (no storage_state) when the file
    doesn't exist yet.
    """
    pw = await async_playwright().start()

    launch_args: dict = {
        "headless": headless,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    }
    if PROXY_URL:
        launch_args["proxy"] = {"server": PROXY_URL}

    browser = await pw.chromium.launch(**launch_args)

    context_args: dict = {
        "user_agent": get_random_user_agent(),
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }
    sp = _session_path_for(platform_key)
    if sp.exists():
        context_args["storage_state"] = str(sp)
        logger.info("[%s] Loading saved session from %s", platform_key, sp)
    else:
        logger.warning(
            "[%s] No saved session at %s — bot will not be logged in",
            platform_key, sp,
        )

    context = await browser.new_context(**context_args)
    await apply_stealth(context)
    page = await context.new_page()
    return pw, browser, context, page


async def save_session(context: BrowserContext, path: str | None = None) -> None:
    sp = Path(PROJECT_ROOT / (path or SESSION_FILE))
    sp.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state()
    sp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.info("Session saved to %s", sp)


async def load_session(browser: Browser, path: str | None = None) -> BrowserContext:
    sp = Path(PROJECT_ROOT / (path or SESSION_FILE))
    if not sp.exists():
        raise FileNotFoundError(f"Session file not found: {sp}")
    context = await browser.new_context(
        storage_state=str(sp),
        user_agent=get_random_user_agent(),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )
    await apply_stealth(context)
    logger.info("Session loaded from %s", sp)
    return context


async def is_session_valid(page: Page) -> bool:
    """Check if the saved cookies still grant a logged-in Yahoo session."""
    try:
        # `commit` est plus tolérant que `domcontentloaded` quand la page enchaîne
        # les redirects/scripts (Cloudflare, RTB Yahoo). On laisse le DOM se stabiliser
        # via les `is_visible(timeout=...)` plus bas.
        await page.goto("https://finance.yahoo.com/", wait_until="commit", timeout=60000)
        await human_delay(3.0, 5.0)

        current_url = page.url
        try:
            current_title = await page.title()
        except Exception:
            current_title = "?"
        logger.info("Loaded — url=%s title=%s", current_url, current_title)

        # Yahoo redirige vers login.yahoo.com (ou la bannière consentement
        # guce.yahoo.com) quand la session est invalide. Sinon on suppose connecté.
        # On évite de matcher des sélecteurs précis (avatar/profile button) car
        # Yahoo les rend via JS après hydratation et change leur markup régulièrement.
        if "login.yahoo.com" in current_url or "guce.yahoo.com" in current_url:
            await page.screenshot(path=str(SCREENSHOTS_DIR / "session_not_logged.png"))
            logger.warning("Redirected to login/consent (%s) — session NOT valid", current_url)
            return False

        if "finance.yahoo.com" in current_url:
            logger.info("Session OK — no redirect to login")
            return True

        # URL inattendue : on capture pour debug et on considère invalide par prudence.
        debug_path = SCREENSHOTS_DIR / "session_check_unexpected.png"
        await page.screenshot(path=str(debug_path), full_page=True)
        logger.warning(
            "Unexpected URL %s — assuming session invalid (screenshot: %s)",
            current_url, debug_path,
        )
        return False

    except Exception as e:
        logger.error("Error checking session validity: %s", e)
        try:
            await page.screenshot(path=str(SCREENSHOTS_DIR / "session_check_error.png"))
        except Exception:
            pass
        return False


async def refresh_session_if_needed(page: Page) -> bool:
    valid = await is_session_valid(page)
    if not valid:
        await notify(
            "Yahoo session expired. Re-run scripts/login.py on the VPS to refresh.",
            level="critical",
        )
    return valid
