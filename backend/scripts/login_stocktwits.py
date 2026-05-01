"""One-shot interactive StockTwits login — opens a headed browser to seed the session.

Usage (from backend/):
  python scripts/login_stocktwits.py

On a headless VPS:
  xvfb-run python scripts/login_stocktwits.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402

from botvmar.browser.session import save_session, _session_path_for  # noqa: E402
from botvmar.browser.stealth import apply_stealth, get_random_user_agent, human_delay  # noqa: E402
from botvmar.utils.logger import get_logger  # noqa: E402

logger = get_logger("login_stocktwits")

_PLATFORM_KEY = "stocktwits"


async def _check_logged_in(page) -> bool:
    """Quick check: are we logged into StockTwits?"""
    try:
        url = page.url
        if "/signin" in url or "/signup" in url:
            return False
        # Look for compose area or user avatar as logged-in indicator
        for sel in [
            'div[contenteditable="true"]',
            '[class*="ComposeForm"]',
            '[class*="UserMenu"]',
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
    print("=" * 50)
    print("  StockTwits — Manual Login")
    print("=" * 50)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
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

    print("Opening StockTwits signin page...")
    # StockTwits sits behind Cloudflare with heavy JS. The default 30s
    # timeout + `domcontentloaded` is too strict — bump to 120s and use
    # `wait_until="commit"` so we don't block on a slow JS bundle. We retry
    # via the homepage as a fallback when /login is rate-limited.
    try:
        await page.goto(
            "https://stocktwits.com/signin",
            wait_until="commit",
            timeout=120_000,
        )
    except Exception as e:
        print(f"  ! /login direct nav failed ({type(e).__name__}: {e}); falling back to homepage")
        await page.goto(
            "https://stocktwits.com/",
            wait_until="commit",
            timeout=120_000,
        )

    print("\n" + "-" * 50)
    print("Log in manually in the browser window.")
    print("Press ENTER here once fully logged in.")
    print("-" * 50)
    input("Press ENTER when you are logged in... ")

    session_path = _session_path_for(_PLATFORM_KEY)
    await save_session(context, str(session_path))

    # Navigate to homepage and validate
    try:
        await page.goto(
            "https://stocktwits.com",
            wait_until="commit",
            timeout=120_000,
        )
    except Exception as e:
        print(f"  ! Homepage nav failed during validation ({e}); skipping check")
    await human_delay(3.0, 5.0)
    valid = await _check_logged_in(page)

    if valid:
        print("\n" + "=" * 50)
        print(f"  Session saved to: {session_path}")
        print("  Start the backend with: python -m botvmar.main")
        print("=" * 50)
    else:
        print("\nWARNING: session saved but validation failed.")
        print("Try starting the bot anyway; if it fails, re-run this script.")

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
