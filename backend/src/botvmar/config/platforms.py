from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from botvmar.db.repositories import platform_settings as platform_settings_repo
from botvmar.utils.logger import get_logger

logger = get_logger("config.platforms")


@dataclass
class PlatformConfig:
    """Snapshot of a single row of `platform_settings`."""

    platform: str
    display_name: str
    enabled: bool
    mode: str                      # "test" | "production"
    reply_enabled: bool
    post_enabled: bool
    ticker: str
    max_replies_per_day: int
    max_posts_per_day: int
    min_post_length: int
    schedule_slots: list[str]      # ["09:00","14:00","19:00"]
    schedule_jitter_min: int
    reply_prompt: str | None
    post_prompt: str | None
    credentials: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def is_test_mode(self) -> bool:
        return self.mode == "test"

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PlatformConfig":
        return cls(
            platform=row["platform"],
            display_name=row["display_name"],
            enabled=bool(row["enabled"]),
            mode=row["mode"] or "test",
            reply_enabled=bool(row["reply_enabled"]),
            post_enabled=bool(row["post_enabled"]),
            ticker=row["ticker"] or "VMAR",
            max_replies_per_day=int(row["max_replies_per_day"] or 0),
            max_posts_per_day=int(row["max_posts_per_day"] or 0),
            min_post_length=int(row["min_post_length"] or 0),
            schedule_slots=list(row["schedule_slots"] or []),
            schedule_jitter_min=int(row["schedule_jitter_min"] or 0),
            reply_prompt=row.get("reply_prompt"),
            post_prompt=row.get("post_prompt"),
            credentials=dict(row.get("credentials") or {}),
            config=dict(row.get("config") or {}),
        )


# Tracks the last set of enabled platforms we INFO-logged. Subsequent calls
# with the same set are quiet (DEBUG only) — the worker hits this multiple
# times per tick and repeated identical INFO lines are pure noise.
_last_logged_enabled: tuple[str, ...] | None = None


async def load_enabled() -> list[PlatformConfig]:
    """Return one `PlatformConfig` per row where `enabled = true`."""
    global _last_logged_enabled

    rows = await platform_settings_repo.get_enabled()
    configs = [PlatformConfig.from_row(r) for r in rows]

    current = tuple(c.platform for c in configs)
    if current != _last_logged_enabled:
        logger.info(
            "Enabled platforms changed: %s",
            ", ".join(current) or "<none>",
        )
        _last_logged_enabled = current
    else:
        logger.debug("Loaded %d enabled platform(s) (unchanged)", len(configs))
    return configs


async def load_one(platform: str) -> PlatformConfig | None:
    row = await platform_settings_repo.get_by_platform(platform)
    return PlatformConfig.from_row(row) if row is not None else None
