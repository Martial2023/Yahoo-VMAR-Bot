"""Repository for `platform_settings` — one row per supported platform.

Schema and seed are owned by Prisma (frontend). Backend reads these rows at
the start of each cycle to know which platforms are enabled and how they
should behave.
"""

from __future__ import annotations

from typing import Any

from botvmar.db.pool import get_pool


async def get_all() -> list[dict[str, Any]]:
    """Return every platform settings row, ordered by id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM platform_settings ORDER BY id"
        )
        return [dict(r) for r in rows]


async def get_enabled() -> list[dict[str, Any]]:
    """Return only the platforms with `enabled = true`."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM platform_settings WHERE enabled = true ORDER BY id"
        )
        return [dict(r) for r in rows]


async def get_by_platform(platform: str) -> dict[str, Any] | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM platform_settings WHERE platform = $1",
            platform,
        )
        return dict(row) if row is not None else None
