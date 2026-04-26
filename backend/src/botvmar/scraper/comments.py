"""Scrape Yahoo Finance community posts for a given ticker."""

from __future__ import annotations

import hashlib
import re

from playwright.async_api import Page

from botvmar.browser.stealth import human_delay
from botvmar.config.env import SCREENSHOTS_DIR
from botvmar.db.repositories import comments as comments_repo
from botvmar.utils.logger import get_logger

logger = get_logger("scraper")

# Sélecteurs possibles pour un post community (Yahoo change le markup).
POST_SELECTORS = [
    '[data-testid="content-card-preview"]',
    '[data-testid="post-card"]',
    '.comment-stream-card',
    'article[data-testid]',
]

_UUID_FROM_URL = re.compile(r"/post/([0-9a-f-]{8,})/?", re.IGNORECASE)


def _generate_comment_id(author: str, text: str) -> str:
    """Fallback ID quand on ne peut pas extraire l'UUID Yahoo natif."""
    raw = f"{author}:{text[:200]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def _navigate_to_community(page: Page, ticker: str) -> str | None:
    """Try multiple Yahoo Finance community URLs, return the working post selector or None."""
    urls = [
        f"https://finance.yahoo.com/quote/{ticker}/community",
        f"https://ca.finance.yahoo.com/quote/{ticker}/community",
    ]

    for url_idx, url in enumerate(urls):
        logger.info("Navigating to %s (attempt %d/%d)", url, url_idx + 1, len(urls))

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as nav_err:
            logger.warning("Navigation failed for %s: %s", url, nav_err)
            if url_idx < len(urls) - 1:
                continue
            return None

        # Attendre que le réseau se stabilise (CSR/Svelte hydratation)
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            logger.debug("networkidle not reached — continuing anyway")

        await human_delay(2.0, 4.0)

        # Cookie / consent banner
        try:
            consent_btn = page.locator(
                'button[name="agree"], [data-testid="consent-accept"]'
            ).first
            if await consent_btn.is_visible(timeout=3000):
                await consent_btn.click()
                await human_delay(1.0, 2.0)
        except Exception:
            pass

        # Scrolls progressifs pour déclencher le lazy-load Svelte
        for scroll_px in (300, 400, 500):
            try:
                await page.evaluate(f"window.scrollBy(0, {scroll_px})")
                await human_delay(1.0, 2.0)
            except Exception:
                pass

        # Attendre qu'au moins un post soit présent dans le DOM
        for sel in POST_SELECTORS:
            try:
                await page.wait_for_selector(sel, timeout=20000)
                logger.info("Posts found with selector: %s", sel)
                return sel
            except Exception:
                continue

        logger.warning("No post found after trying all selectors on %s", url)

    return None


async def scrape_comments(page: Page, ticker: str) -> list[dict]:
    """Scrape les posts visibles sur la page community Yahoo Finance.

    Yahoo a migré vers un format "post" (style fil social) ; on conserve la
    nomenclature "comment" en interne pour ne pas casser le reste du code.
    """
    try:
        active_selector = await _navigate_to_community(page, ticker)

        if active_selector is None:
            logger.warning("Could not find any posts — saving debug info")
            try:
                await page.screenshot(
                    path=str(SCREENSHOTS_DIR / "no_comments_container.png"),
                    full_page=True,
                    timeout=10000,
                )
            except Exception:
                pass
            try:
                html = await page.content()
                (SCREENSHOTS_DIR / "no_comments_container.html").write_text(
                    html[:500_000], encoding="utf-8"
                )
            except Exception:
                pass
            return []

        # Scroll progressif pour charger les posts paginés
        for i in range(4):
            await page.evaluate("window.scrollBy(0, 800)")
            await human_delay(1.5, 3.0)
            logger.debug("Scroll %d/4 done", i + 1)

        posts = page.locator(active_selector)
        count = await posts.count()
        logger.info("Found %d posts on page", count)

        comments: list[dict] = []
        for i in range(count):
            try:
                el = posts.nth(i)

                # ID natif Yahoo : extrait du data-url="…/post/<UUID>/"
                post_id = ""
                try:
                    data_url = await el.get_attribute("data-url")
                    if data_url:
                        m = _UUID_FROM_URL.search(data_url)
                        if m:
                            post_id = m.group(1)
                except Exception:
                    pass

                # Auteur (nom affiché — premier label-bold dans user-block)
                author = ""
                try:
                    a = el.locator(
                        '[data-testid="user-block"] .type-label-lg-bold'
                    ).first
                    txt = await a.text_content(timeout=1500)
                    author = (txt or "").strip()
                except Exception:
                    pass

                # Texte : concaténer tous les <p> de .formatted-text
                text = ""
                try:
                    paragraphs = el.locator(".formatted-text p")
                    n = await paragraphs.count()
                    parts: list[str] = []
                    for j in range(n):
                        t = await paragraphs.nth(j).text_content(timeout=500)
                        if t:
                            parts.append(t.strip())
                    text = " ".join(parts).strip()
                except Exception:
                    pass

                if not text:
                    continue

                # Date relative (ex: "Apr 23")
                date_str = ""
                try:
                    d = el.locator(
                        '[data-testid="user-block-timestamp"]'
                    ).first
                    txt = await d.text_content(timeout=500)
                    date_str = (txt or "").strip()
                except Exception:
                    pass

                # Upvotes (le span à côté de l'icône upvote)
                likes = 0
                try:
                    txt = await el.locator(
                        '[data-testid="vote-action"] span'
                    ).first.text_content(timeout=500)
                    if txt and txt.strip().isdigit():
                        likes = int(txt.strip())
                except Exception:
                    pass

                # Nombre de réponses (sous le bouton Comment)
                comment_count = 0
                try:
                    txt = await el.locator(
                        '[data-testid="comment-action"] span'
                    ).first.text_content(timeout=500)
                    if txt and txt.strip().isdigit():
                        comment_count = int(txt.strip())
                except Exception:
                    pass

                comment_id = post_id or _generate_comment_id(author, text)
                comments.append({
                    "id": comment_id,
                    "author": author,
                    "text": text,
                    "date": date_str,
                    "likes": likes,
                    "dislikes": 0,  # Yahoo n'a plus de dislike sur les posts
                    "comment_count": comment_count,
                    "element_index": i,
                    "_selector": active_selector,
                })
            except Exception as e:
                logger.debug("Error parsing post %d: %s", i, e)
                continue

        logger.info("Scraped %d posts total", len(comments))
        return comments

    except Exception as e:
        logger.error("Error scraping community page: %s", e)
        try:
            await page.screenshot(
                path=str(SCREENSHOTS_DIR / "scrape_error.png"),
                timeout=10000,
            )
        except Exception:
            pass
        return []


async def filter_new(scraped: list[dict]) -> list[dict]:
    """Renvoie les posts pas encore vus, et les marque vus en BDD."""
    new_comments: list[dict] = []
    for c in scraped:
        if not await comments_repo.is_seen(c["id"]):
            new_comments.append(c)
            await comments_repo.mark_seen(c["id"], c.get("author", ""), c.get("text", ""))
    logger.info(
        "Found %d new posts out of %d scraped", len(new_comments), len(scraped)
    )
    return new_comments
