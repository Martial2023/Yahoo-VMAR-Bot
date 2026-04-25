"""Asyncpg connection pool — single shared instance for the whole process."""

from __future__ import annotations

import asyncpg

from botvmar.config.env import DATABASE_URL
from botvmar.utils.logger import get_logger

logger = get_logger("db.pool")

_pool: asyncpg.Pool | None = None


async def init_pool(min_size: int = 1, max_size: int = 10) -> asyncpg.Pool:
    """Create the global pool. Idempotent."""
    global _pool
    if _pool is not None:
        return _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in .env")
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
    )
    logger.info("Postgres pool initialized (min=%d max=%d)", min_size, max_size)
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() first")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres pool closed")
