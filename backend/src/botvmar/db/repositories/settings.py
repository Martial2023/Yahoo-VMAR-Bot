"""Repository for the singleton `bot_settings` table.

Schema and seed are owned by Prisma (frontend). Backend reads only.
"""

from __future__ import annotations

from typing import Any

from botvmar.db.pool import get_pool


async def get_settings() -> dict[str, Any]:
    """Return the singleton settings row (id = 1)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM bot_settings WHERE id = 1")
        if row is None:
            raise RuntimeError(
                "bot_settings row not found — run the Prisma seed from the frontend "
                "(`pnpm prisma db seed`) before starting the backend"
            )
        return dict(row)
