"""Run a single bot cycle for one platform, in isolation.

Why a separate module from `bot_service`?
  - `bot_service` is the multi-platform orchestrator (gathers, schedules,
    aggregates errors). `platform_runner` is the per-platform pipeline
    (init adapter → fetch posts → reply → optionally post → cleanup).
  - One platform crashing must NOT abort the others. The orchestrator wraps
    each `run_platform_cycle()` in try/except; `platform_runner` itself uses
    the per-call error contract of the adapter (return False, never raise).
"""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from botvmar.adapters.base import (
    PlatformAdapter,
    PlatformAuthError,
    PlatformError,
    Post,
)
from botvmar.ai.responder import generate_post, generate_reply
from botvmar.config.platforms import PlatformConfig
from botvmar.db.pool import get_pool
from botvmar.db.repositories import activities, runs, whitelist
from botvmar.db.repositories import comments as comments_repo
from botvmar.scheduling.skip_rules import SkipRules
from botvmar.utils.logger import get_logger
from botvmar.utils.notifier import notify

logger = get_logger("service.platform_runner")

async def _count_recent(
    platform: str,
    activity_type: str,
    status: str,
    since: timedelta,
) -> int:
    """Count successful actions of the given type for `platform` in the window."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT COUNT(*) FROM bot_activities
            WHERE platform = $1
              AND type = $2
              AND status = $3
              AND created_at > NOW() - $4::interval
            """,
            platform, activity_type, status, since,
        ) or 0


async def replies_today(platform: str) -> int:
    return await _count_recent(platform, "reply", "success", timedelta(days=1))


async def posts_today(platform: str) -> int:
    return await _count_recent(platform, "post", "success", timedelta(days=1))


async def _filter_new(platform: str, posts: list[Post]) -> list[Post]:
    """Drop posts already in `seen_comments` and persist new ones."""
    new: list[Post] = []
    for p in posts:
        if not await comments_repo.is_seen(p.id, platform=platform):
            new.append(p)
            await comments_repo.mark_seen(
                p.id, p.author, p.text, platform=platform,
            )
    logger.info(
        "[%s] %d new posts out of %d scraped",
        platform, len(new), len(posts),
    )
    return new


async def _is_allowed_to_reply(
    platform_config: PlatformConfig,
    adapter: PlatformAdapter,
    post: Post,
    whitelisted: set[str],
    skip_rules: SkipRules,
) -> tuple[bool, str | None]:
    """Return (allowed, skip_reason). `skip_reason` is None when allowed."""
    # 1. Adapter-level skip (built-in official accounts, etc.)
    if adapter.should_skip_author(post.author):
        return False, "skip_author_builtin"
    # 2. Config-driven author skip list
    if skip_rules.author_blocked(post.author):
        return False, "skip_author_config"
    # 3. Config-driven keyword skip list
    if skip_rules.keyword_blocked(post.text):
        return False, "skip_keyword"
    # 4. Minimum length
    if skip_rules.too_short(post.text):
        return False, "too_short"
    # 5. Test mode: whitelist gate
    if platform_config.is_test_mode:
        if post.author.strip().lower() not in whitelisted:
            return False, "not_whitelisted"
    return True, None


async def run_platform_cycle(
    platform_config: PlatformConfig,
    *,
    triggered_by: str = "schedule",
    shutdown_flag=lambda: False,
) -> dict[str, int]:
    """Run one full cycle for one platform. Returns counters."""
    platform = platform_config.platform
    counters = {"scraped": 0, "replies": 0, "posts": 0, "errors": 0}

    if not platform_config.enabled:
        logger.info("[%s] disabled — skipping", platform)
        return counters

    run_id = await runs.start(triggered_by=triggered_by, platform=platform)
    adapter = None

    try:
        from botvmar.adapters.registry import build_adapter
        adapter = build_adapter(platform_config)
        if adapter is None:
            await activities.log(
                run_id=run_id, platform=platform, type="error", status="failed",
                error_msg="no_adapter_registered",
            )
            counters["errors"] += 1
            return counters

        try:
            await adapter.init()
        except PlatformAuthError as e:
            logger.warning("[%s] auth error: %s", platform, e)
            await activities.log(
                run_id=run_id, platform=platform, type="session", status="failed",
                error_msg=str(e)[:1000],
            )
            counters["errors"] += 1
            return counters

        logger.info("[%s] fetching posts for ticker=%s", platform, platform_config.ticker)
        all_posts = await adapter.fetch_posts(platform_config.ticker)
        counters["scraped"] = len(all_posts)
        await activities.log(
            run_id=run_id, platform=platform, type="scrape",
            status="success" if all_posts else "skipped",
            metadata={"count": len(all_posts)},
        )

        new_posts = await _filter_new(platform, all_posts) if all_posts else []

        whitelisted = await whitelist.get_handles(platform) if platform_config.is_test_mode else set()
        skip_rules = SkipRules.from_config(platform_config)

        if platform_config.reply_enabled and new_posts:
            already = await replies_today(platform)
            available = max(0, platform_config.max_replies_per_day - already)
            logger.info(
                "[%s] reply budget: %d/%d used today (%d available)",
                platform, already, platform_config.max_replies_per_day, available,
            )

            for post in new_posts:
                if shutdown_flag() or available <= 0:
                    break

                allowed, skip_reason = await _is_allowed_to_reply(
                    platform_config, adapter, post, whitelisted, skip_rules,
                )
                if not allowed:
                    logger.debug("[%s] skip %s by %s: %s",
                                 platform, post.id, post.author, skip_reason)
                    await activities.log(
                        run_id=run_id, platform=platform, type="reply", status="skipped",
                        comment_id=post.id, error_msg=skip_reason,
                    )
                    continue

                reply_text = await generate_reply(post.text, post.author)
                if not reply_text:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, platform=platform, type="reply", status="failed",
                        comment_id=post.id, error_msg="ai_generation_failed",
                    )
                    continue

                ok = await adapter.reply_to(post, reply_text)
                if ok:
                    counters["replies"] += 1
                    available -= 1
                    await activities.log(
                        run_id=run_id, platform=platform, type="reply", status="success",
                        comment_id=post.id, content=reply_text,
                    )
                else:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, platform=platform, type="reply", status="failed",
                        comment_id=post.id, content=reply_text,
                        error_msg="post_failed",
                    )

                if available > 0 and not shutdown_flag():
                    await asyncio.sleep(random.uniform(60, 180))

        # ----- Proactive post ---------------------------------------------
        if platform_config.post_enabled and not shutdown_flag():
            today_posts = await posts_today(platform)
            logger.info(
                "[%s] post budget: %d/%d used today",
                platform, today_posts, platform_config.max_posts_per_day,
            )

            if today_posts < platform_config.max_posts_per_day and random.random() < 0.3:
                post_text = await generate_post()
                if post_text:
                    ok = await adapter.create_post(platform_config.ticker, post_text)
                    if ok:
                        counters["posts"] += 1
                        await activities.log(
                            run_id=run_id, platform=platform, type="post", status="success",
                            content=post_text,
                        )
                    else:
                        counters["errors"] += 1
                        await activities.log(
                            run_id=run_id, platform=platform, type="post", status="failed",
                            content=post_text, error_msg="post_failed",
                        )
                else:
                    counters["errors"] += 1
                    await activities.log(
                        run_id=run_id, platform=platform, type="post", status="failed",
                        error_msg="ai_generation_failed",
                    )

    except PlatformError as e:
        logger.error("[%s] platform error: %s", platform, e, exc_info=True)
        counters["errors"] += 1
        await activities.log(
            run_id=run_id, platform=platform, type="error", status="failed",
            error_msg=str(e)[:1000],
        )
        await notify(f"[{platform}] platform error: {e}", level="error")

    except Exception as e:
        logger.error("[%s] unexpected error: %s", platform, e, exc_info=True)
        counters["errors"] += 1
        await activities.log(
            run_id=run_id, platform=platform, type="error", status="failed",
            error_msg=str(e)[:1000],
        )
        await notify(f"[{platform}] unexpected error: {e}", level="error")

    finally:
        if adapter is not None:
            try:
                await adapter.cleanup()
            except Exception as e:
                logger.debug("[%s] cleanup error (ignored): %s", platform, e)

        await runs.finish(
            run_id,
            status=("failed"
                    if counters["errors"] and not (counters["replies"] or counters["posts"])
                    else "success"),
            comments_scraped=counters["scraped"],
            replies_posted=counters["replies"],
            posts_published=counters["posts"],
            errors_count=counters["errors"],
        )
        logger.info(
            "[%s] cycle finished — scraped=%d replies=%d posts=%d errors=%d",
            platform,
            counters["scraped"], counters["replies"], counters["posts"], counters["errors"],
        )

    return counters
