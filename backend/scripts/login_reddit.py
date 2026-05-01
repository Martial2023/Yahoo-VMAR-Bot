"""Reddit session capture — login via Firefox to bypass Chrome App-Bound encryption.

Chrome v127+ encrypts cookies with App-Bound keys that cannot be extracted
externally, and blocks --remote-debugging-port on the default user-data-dir.
Firefox has none of these restrictions.

This script launches Firefox (via Playwright), lets you log into Reddit
manually, then saves the cookies in Playwright storage-state format.
The bot will later inject these cookies into its Chromium browser.

Usage (from backend/):
  python scripts/login_reddit.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402

from botvmar.browser.session import _session_path_for  # noqa: E402
from botvmar.browser.stealth import human_delay  # noqa: E402
from botvmar.utils.logger import get_logger  # noqa: E402

logger = get_logger("login_reddit")

_PLATFORM_KEY = "reddit"


async def _check_logged_in(page) -> bool:
    """Quick check: are we logged into Reddit?"""
    try:
        url = page.url
        if "/login" in url or "/register" in url:
            return False
        for sel in [
            '#USER_DROPDOWN_ID',
            'button[aria-label="User menu"]',
            'faceplate-tracker[noun="create_post"]',
            'header button:has(img)',
            '[id*="header-action-items"]',
        ]:
            try:
                if await page.locator(sel).first.is_visible(timeout=3000):
                    return True
            except Exception:
                continue
        # No login redirect — assume OK
        return True
    except Exception:
        return False


async def main() -> None:
    print("=" * 60)
    print("  Reddit — Login via Firefox")
    print("=" * 60)
    print()
    print("  Firefox will open — Reddit cannot detect it as a bot.")
    print("  Log in manually, then come back here.\n")

    pw = await async_playwright().start()

    # Firefox doesn't suffer from Chrome's App-Bound encryption
    # or bot detection on Reddit's login page.
    browser = await pw.firefox.launch(
        headless=False,
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        timezone_id="America/New_York",
    )
    page = await context.new_page()

    print("  Opening Reddit login page...")
    try:
        await page.goto(
            "https://www.reddit.com/login/",
            wait_until="domcontentloaded",
            timeout=120_000,
        )
    except Exception as e:
        print(f"  ! Navigation failed ({e}), trying homepage...")
        await page.goto(
            "https://www.reddit.com/",
            wait_until="domcontentloaded",
            timeout=120_000,
        )

    print()
    print("-" * 60)
    print("  Log in to Reddit in the Firefox window.")
    print("  Once you see the Reddit homepage (logged in),")
    print("  come back here and press ENTER.")
    print("-" * 60)
    input("\n  Press ENTER when you are logged in... ")

    # Verify login
    # Navigate to homepage to check
    try:
        await page.goto(
            "https://www.reddit.com/",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
    except Exception:
        pass
    await human_delay(3.0, 5.0)

    logged_in = await _check_logged_in(page)

    if not logged_in:
        print("\n  Doesn't look like you're logged in yet.")
        print("  Try logging in now, then press ENTER again.")
        input("\n  Press ENTER... ")
        logged_in = await _check_logged_in(page)

    # Save session — Firefox storage_state contains cookies that
    # Playwright can later inject into any browser (including Chromium).
    session_path = _session_path_for(_PLATFORM_KEY)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state()
    session_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Count Reddit cookies
    reddit_cookies = [c for c in state.get("cookies", []) if "reddit" in c.get("domain", "")]
    print(f"\n  Saved {len(reddit_cookies)} Reddit cookies to {session_path}")

    if logged_in and reddit_cookies:
        print("\n" + "=" * 60)
        print("  Session captured successfully!")
        print(f"  File: {session_path}")
        print()
        print("  Enable Reddit in the dashboard or run:")
        print("    UPDATE platform_settings SET enabled=true WHERE platform='reddit';")
        print("=" * 60)
    elif reddit_cookies:
        print("\n  Session saved but login could not be verified.")
        print("  Try enabling Reddit anyway.")
    else:
        print("\n  WARNING: No Reddit cookies found in the session.")
        print("  Make sure you logged in successfully and try again.")

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
