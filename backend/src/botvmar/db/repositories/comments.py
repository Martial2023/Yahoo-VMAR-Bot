"""Repository for `seen_comments` — tracks comments already processed (per platform)."""

from __future__ import annotations

from botvmar.db.pool import get_pool


async def is_seen(comment_id: str, platform: str = "yahoo_finance") -> bool:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT 1 FROM seen_comments WHERE id = $1 AND platform = $2",
            comment_id, platform,
        )
        return row is not None


async def mark_seen(
    comment_id: str,
    author: str,
    content: str,
    platform: str = "yahoo_finance",
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO seen_comments (id, platform, author, content, scraped_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (id) DO NOTHING
            """,
            comment_id, platform, author, content,
        )
