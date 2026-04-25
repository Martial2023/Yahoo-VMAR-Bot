"""Anti-detection — stealth, user-agent rotation, human-like delays/typing."""

from __future__ import annotations

import asyncio
import random

from playwright.async_api import BrowserContext, Page
from playwright_stealth import Stealth

from botvmar.utils.logger import get_logger

_stealth = Stealth()

logger = get_logger("stealth")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    return random.choice(USER_AGENTS)


async def apply_stealth(context: BrowserContext) -> None:
    for page in context.pages:
        await _stealth.apply_stealth_async(page)
    context.on("page", lambda page: asyncio.ensure_future(_stealth.apply_stealth_async(page)))
    logger.debug("Stealth applied to browser context")


async def human_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def human_type(page: Page, selector: str, text: str) -> None:
    element = page.locator(selector)
    await element.click()
    await human_delay(0.3, 0.7)
    for char in text:
        await element.press_sequentially(char, delay=random.randint(50, 150))
    logger.debug("Typed %d characters into %s", len(text), selector)


async def human_click(page: Page, selector: str) -> None:
    element = page.locator(selector)
    box = await element.bounding_box()
    if box:
        x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
        y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await human_delay(0.2, 0.5)
        await page.mouse.click(x, y)
    else:
        await element.click()
    logger.debug("Clicked on %s", selector)
