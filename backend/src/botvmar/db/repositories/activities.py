"""Repository for `bot_activities` — granular event log feeding the dashboard."""

from __future__ import annotations

import json
from typing import Any

from botvmar.db.pool import get_pool


async def log(
    *,
    type: str,
    status: str,
    platform: str | None = None,
    run_id: str | None = None,
    comment_id: str | None = None,
    content: str | None = None,
    error_msg: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert one activity event.

    type: "scrape" | "reply" | "post" | "login" | "session" | "error"
    status: "success" | "failed" | "skipped"
    platform: lowercase adapter name ("yahoo_finance", "reddit", ...) or None
              for global events (process startup, signal handler, ...).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO bot_activities
              (run_id, platform, type, status, comment_id, content, error_msg, metadata, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, NOW())
            """,
            run_id, platform, type, status, comment_id, content, error_msg,
            json.dumps(metadata) if metadata is not None else None,
        )
