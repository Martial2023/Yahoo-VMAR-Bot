"""Bot cycle orchestration — scrape, reply, post, log everything to Postgres."""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from botvmar.ai.responder import generate_post, generate_reply
from botvmar.browser.session import create_browser, refresh_session_if_needed
from botvmar.config import runtime
from botvmar.db.repositories import activities, runs
from botvmar.poster.actions import post_new_comment, reply_to_comment
from botvmar.scraper.comments import filter_new, scrape_comments
from botvmar.utils.logger import get_logger
from botvmar.utils.notifier import notify

logger = get_logger("service.bot")


async def _count_recent(activity_type: str, status: str, since: timedelta) -> int:
    """Count rows in `bot_activities` of given type/status within `since` ago.

    asyncpg encode `interval` à partir d'un `datetime.timedelta`, pas d'une string.
    """
    from botvmar.db.pool import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*) FROM bot_activities
            WHERE type = $1 AND status = $2
              AND created_at > NOW() - $3::interval
            """,
            activity_type, status, since,
        )


async def replies_last_hour() -> int:
    return await _count_recent("reply", "success", timedelta(hours=1))


async def posts_today() -> int:
    return await _count_recent("post", "success", timedelta(days=1))


async def run_cycle(triggered_by: str = "schedule", shutdown_flag=lambda: False) -> None:
    """Run a single bot cycle. Reads runtime settings fresh."""
    settings = await runtime.load()  # always fresh at cycle start

    if not settings.bot_enabled:
        logger.info("Bot disabled in settings — skipping cycle")
        await activities.log(type="scrape", status="skipped", error_msg="bot_enabled=false")
        return

    run_id = await runs.start(triggered_by=triggered_by)
    counters = {"scraped": 0, "replies": 0, "posts": 0, "errors": 0}
    pw = browser = None

    try:
        pw, browser, _, page = await create_browser(headless=True)

        if not await refresh_session_if_needed(page):
            logger.warning("Session expired — aborting cycle")
            await activities.log(
                run_id=run_id, type="session", status="failed",
                error_msg="session_expired",
            )
            counters["errors"] += 1
            return

        logger.info("Scraping comments for %s", settings.ticker)
        all_comments = await scrape_comments(page, settings.ticker)
        counters["scraped"] = len(all_comments)
        await activities.log(
            run_id=run_id, type="scrape",
            status="success" if all_comments else "skipped",
            metadata={"count": len(all_comments)},
        )

        if not all_comments:
            return

        new_comments = await filter_new(all_comments)
        logger.info("New comments to process: %d", len(new_comments))

        # --- REPLIES ---
        if settings.mode in ("reply", "both") and new_comments:
            already = await replies_last_hour()
            available = settings.max_replies_per_hour - already
            logger.info("Replies budget: %d/%d used this hour", already, settings.max_replies_per_hour)

            for c in new_comments:
                if shutdown_flag():
                    break
                if available <= 0:
                    logger.info("Reply quota reached")
                    break
                if len(c["text"]) < 20:
                    logger.debug("Skipping short comment (%d chars)", len(c["text"]))
                    continue

                reply_text = await generate_reply(c["text"], c["author"])
                if not reply_text:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, type="reply", status="failed",
                        comment_id=c["id"], error_msg="ai_generation_failed",
                    )
                    continue

                ok = await reply_to_comment(page, c["_selector"], c["element_index"], reply_text)
                if ok:
                    counters["replies"] += 1
                    available -= 1
                    await activities.log(
                        run_id=run_id, type="reply", status="success",
                        comment_id=c["id"], content=reply_text,
                    )
                    logger.info("Reply posted (%d remaining this hour)", available)
                else:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, type="reply", status="failed",
                        comment_id=c["id"], content=reply_text,
                        error_msg="post_failed",
                    )

                if available > 0 and not shutdown_flag():
                    await asyncio.sleep(random.uniform(60, 180))

        # --- PROACTIVE POST ---
        if settings.mode in ("post", "both") and not shutdown_flag():
            today_count = await posts_today()
            logger.info("Posts budget: %d/%d used today", today_count, settings.max_posts_per_day)

            if today_count < settings.max_posts_per_day and random.random() < 0.3:
                post_text = await generate_post()
                if post_text:
                    ok = await post_new_comment(page, settings.ticker, post_text)
                    if ok:
                        counters["posts"] += 1
                        await activities.log(
                            run_id=run_id, type="post", status="success",
                            content=post_text,
                        )
                        logger.info("Proactive post published")
                    else:
                        counters["errors"] += 1
                        await activities.log(
                            run_id=run_id, type="post", status="failed",
                            content=post_text, error_msg="post_failed",
                        )
                else:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, type="post", status="failed",
                        error_msg="ai_generation_failed",
                    )

    except Exception as e:
        logger.error("Error in bot cycle: %s", e, exc_info=True)
        counters["errors"] += 1
        await activities.log(
            run_id=run_id, type="error", status="failed",
            error_msg=str(e)[:1000],
        )
        await notify(f"Bot cycle error: {e}", level="error")

    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass

        await runs.finish(
            run_id,
            status="failed" if counters["errors"] and counters["replies"] == 0 and counters["posts"] == 0 else "success",
            comments_scraped=counters["scraped"],
            replies_posted=counters["replies"],
            posts_published=counters["posts"],
            errors_count=counters["errors"],
        )
        logger.info(
            "Cycle finished — scraped=%d replies=%d posts=%d errors=%d",
            counters["scraped"], counters["replies"], counters["posts"], counters["errors"],
        )
