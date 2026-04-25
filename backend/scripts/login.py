"""One-shot interactive Yahoo login — opens a headed browser to seed the session.

Usage (from backend/):
  python scripts/login.py

On a headless VPS:
  xvfb-run python scripts/login.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running this script without `pip install -e .`
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402

from botvmar.browser.session import is_session_valid, save_session  # noqa: E402
from botvmar.browser.stealth import apply_stealth, get_random_user_agent  # noqa: E402
from botvmar.config.env import PROJECT_ROOT, SESSION_FILE  # noqa: E402
from botvmar.utils.logger import get_logger  # noqa: E402

logger = get_logger("login")


async def main() -> None:
    print("=" * 50)
    print("  Yahoo Finance — Manual Login")
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

    print("Opening Yahoo login page...")
    await page.goto("https://login.yahoo.com", wait_until="domcontentloaded")

    print("\n" + "-" * 50)
    print("Log in manually in the browser window.")
    print("Press ENTER here once fully logged in.")
    print("-" * 50)
    input("Press ENTER when you are logged in... ")

    await save_session(context)
    valid = await is_session_valid(page)

    session_path = PROJECT_ROOT / SESSION_FILE
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
