"""Repository for `bot_runs` — one row per bot cycle, used for dashboard graphs."""

from __future__ import annotations

import secrets
from datetime import datetime

from botvmar.db.pool import get_pool


def _new_id() -> str:
    return secrets.token_urlsafe(12)


async def last_started_at(platform: str) -> datetime | None:
    """Most recent `started_at` for `platform`, or None when no run yet."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT MAX(started_at) FROM bot_runs WHERE platform = $1",
            platform,
        )


async def start(triggered_by: str = "schedule", platform: str = "yahoo_finance") -> str:
    """Open a new run row and return its id."""
    run_id = _new_id()
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_runs
              (id, platform, started_at, status, comments_scraped, replies_posted,
               posts_published, errors_count, triggered_by)
            VALUES ($1, $2, NOW(), 'running', 0, 0, 0, 0, $3)
            """,
            run_id, platform, triggered_by,
        )
    return run_id


async def finish(
    run_id: str,
    *,
    status: str,
    comments_scraped: int,
    replies_posted: int,
    posts_published: int,
    errors_count: int,
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE bot_runs SET
              ended_at = NOW(),
              status = $2,
              comments_scraped = $3,
              replies_posted = $4,
              posts_published = $5,
              errors_count = $6
            WHERE id = $1
            """,
            run_id, status, comments_scraped, replies_posted,
            posts_published, errors_count,
        )
