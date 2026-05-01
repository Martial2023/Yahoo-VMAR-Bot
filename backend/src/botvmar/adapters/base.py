"""Platform adapter contract.

Every supported platform (Yahoo Finance, Reddit, StockTwits, …) implements
this interface. The orchestrator (`services.bot_service`) only sees this
abstraction and never depends on platform-specific details.

Lifecycle of an adapter during one cycle:
    1. `init()`       — open browser / OAuth client / load cookies
    2. `health()`     — verify the session is usable (cheap probe)
    3. `fetch_posts()`— normalized list of posts mentioning the ticker
    4. `reply_to()`   — post a reply under one of the fetched posts
    5. `create_post()`— optional proactive post on the platform
    6. `cleanup()`    — close browser / release resources

Errors are surfaced through `PlatformError` (and subclasses). The orchestrator
catches them per-platform so a Reddit failure cannot stop Yahoo from running.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class Post:
    """A platform-agnostic representation of a post / message / comment.

    Adapters MUST return their scraped items as `Post` instances so the
    orchestrator can treat all platforms uniformly.

    Attributes
    ----------
    id : str
        Stable, platform-unique identifier. Used as the dedup key in
        `seen_comments`. Prefer the platform's native UUID; fall back to a
        deterministic hash of (author + first 200 chars of text).
    platform : str
        Lowercase platform key, e.g. "yahoo_finance", "reddit". Must match
        `PlatformAdapter.name`.
    author : str
        Display name or handle of the post's author.
    text : str
        Full text content of the post.
    url : str | None
        Permalink to the post when available (helpful for the dashboard).
    created_at : datetime | None
        Creation timestamp when the platform exposes it.
    likes : int
        Upvotes / hearts / likes — 0 when not applicable.
    reply_count : int
        Number of replies/comments under this post.
    raw : dict
        Free-form bag for adapter-internal data needed when replying
        (DOM selectors, Reddit `submission` object, etc.). Never persisted.
    """

    id: str
    platform: str
    author: str
    text: str
    url: str | None = None
    created_at: datetime | None = None
    likes: int = 0
    reply_count: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class PlatformError(Exception):
    """Generic platform failure. Caught per-adapter by the orchestrator."""


class PlatformAuthError(PlatformError):
    """Session/credentials are invalid or expired — operator action needed."""


class PlatformRateLimitError(PlatformError):
    """Platform throttled us — back off and try later."""


class PlatformAdapter(ABC):
    """Abstract base class every platform adapter must implement.

    Implementations are stateful within a single cycle: `init()` opens
    resources, all subsequent calls reuse them, `cleanup()` tears them down.
    """

    #: Lowercase identifier — also the value stored in the `platform` column
    #: of `bot_activities`, `bot_runs`, `seen_comments`, etc.
    name: str = ""

    #: Human-readable label for dashboards and notifications.
    display_name: str = ""

    @abstractmethod
    async def init(self) -> None:
        """Acquire any resources needed for this cycle (browser, OAuth, …).

        Raises
        PlatformAuthError
            When credentials are missing or the session cannot be restored.
        """

    @abstractmethod
    async def cleanup(self) -> None:
        """Release resources opened in `init()`. Must be idempotent and never
        raise — the orchestrator calls it from a `finally` block."""

    async def health(self) -> bool:
        """Cheap probe — return True when the adapter is ready to operate.

        Default implementation returns True; subclasses override when they
        can perform a sub-second check (e.g. ping an API endpoint)."""
        return True

    @abstractmethod
    async def fetch_posts(self, ticker: str) -> list[Post]:
        """Return posts mentioning `ticker` published since the last cycle.

        The orchestrator filters out already-seen ids before doing anything,
        so adapters can return everything they find without dedup logic.
        """

    @abstractmethod
    async def reply_to(self, post: Post, text: str) -> bool:
        """Post `text` as a reply under `post`. Return True on success.

        Implementations should NOT raise on user-level failures (button not
        found, rate limit on a single post, etc.) — return False instead so
        the orchestrator can log and continue.
        """

    @abstractmethod
    async def create_post(self, ticker: str, text: str) -> bool:
        """Publish a brand-new top-level post about `ticker`. Return True on
        success. Same error contract as `reply_to`.

        Some platforms (e.g. Reddit) require a title — adapters extract one
        from `text` or from a per-platform setting.
        """

    def should_skip_author(self, author: str) -> bool:
        """Per-platform skip list (official accounts, blocked users, …).

        Default implementation returns False. Adapters override to filter
        their own platform's official handles.
        """
        return False
