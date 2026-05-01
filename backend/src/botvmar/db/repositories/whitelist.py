"""Repository for `whitelisted_authors` — authors the bot may reply to in test mode.

Author handles are normalized to lowercase + stripped before storage and
lookup, so the dashboard can pass them in any casing.
"""

from __future__ import annotations

from typing import Any

from botvmar.db.pool import get_pool


def _norm(handle: str) -> str:
    return (handle or "").strip().lower()


async def get_handles(platform: str) -> set[str]:
    """Return the set of whitelisted author handles for `platform` (lowercased)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT author_handle FROM whitelisted_authors WHERE platform = $1",
            platform,
        )
        return {_norm(r["author_handle"]) for r in rows if r["author_handle"]}


async def list_entries(platform: str | None = None) -> list[dict[str, Any]]:
    """Return full rows, optionally filtered by platform, ordered by creation."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if platform is None:
            rows = await conn.fetch(
                "SELECT * FROM whitelisted_authors ORDER BY platform, created_at"
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM whitelisted_authors WHERE platform = $1 ORDER BY created_at",
                platform,
            )
    return [dict(r) for r in rows]


async def is_whitelisted(platform: str, author: str) -> bool:
    if not author:
        return False
    handles = await get_handles(platform)
    return _norm(author) in handles


async def add(platform: str, author_handle: str, note: str | None = None) -> None:
    """Insert (platform, author_handle). Idempotent."""
    handle = _norm(author_handle)
    if not handle:
        raise ValueError("author_handle must be a non-empty string")

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO whitelisted_authors (platform, author_handle, note, created_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (platform, author_handle) DO NOTHING
            """,
            platform, handle, note,
        )


async def remove(platform: str, author_handle: str) -> int:
    """Delete one entry. Returns the number of rows deleted (0 or 1)."""
    handle = _norm(author_handle)
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM whitelisted_authors WHERE platform = $1 AND author_handle = $2",
            platform, handle,
        )
    # asyncpg returns "DELETE n"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0
