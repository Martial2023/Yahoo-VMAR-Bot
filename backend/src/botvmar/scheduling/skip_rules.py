"""Per-post skip rules — applied by `platform_runner` before generating a reply.

Rules are layered:
  1. Adapter-level: `adapter.should_skip_author(author)` — built-in skip list
     (e.g. official VMAR account on Yahoo Finance).
  2. Config-driven: `platform_settings.config.skipAuthors` — operator-managed
     extension of the author skip list, editable from the dashboard without
     redeploying.
  3. Config-driven: `platform_settings.config.skipKeywords` — substring
     match (case-insensitive) on the post text.
  4. Config-driven: `platform_settings.config.minPostLength` — falls back to
     the column-level `min_post_length` when missing.

A single dataclass `SkipRules` is built once per cycle and queried per post,
so we don't repeatedly parse the JSON config inside the inner loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from botvmar.config.platforms import PlatformConfig


@dataclass
class SkipRules:
    """Pre-computed per-cycle skip rules for one platform."""

    skip_authors: set[str]      # lowercased
    skip_keywords: list[str]    # lowercased
    min_post_length: int

    @classmethod
    def from_config(cls, config: PlatformConfig) -> "SkipRules":
        cfg = config.config or {}
        # `skipAuthors` is the JSON key the dashboard writes; tolerate snake_case too.
        raw_authors = cfg.get("skipAuthors") or cfg.get("skip_authors") or []
        raw_keywords = cfg.get("skipKeywords") or cfg.get("skip_keywords") or []

        return cls(
            skip_authors={(a or "").strip().lower() for a in raw_authors if a},
            skip_keywords=[(k or "").strip().lower() for k in raw_keywords if k],
            min_post_length=int(
                cfg.get("minPostLength")
                or cfg.get("min_post_length")
                or config.min_post_length
                or 0
            ),
        )

    def author_blocked(self, author: str) -> bool:
        """True when `author` matches any entry in the config-driven skip list.

        Match is "contains" (lowercased) so an entry "vision marine" catches
        both "Vision Marine" and "vision marine official".
        """
        if not author:
            return False
        a = author.strip().lower()
        return any(blocked in a for blocked in self.skip_authors)

    def keyword_blocked(self, text: str) -> bool:
        if not text or not self.skip_keywords:
            return False
        t = text.lower()
        return any(kw in t for kw in self.skip_keywords)

    def too_short(self, text: str) -> bool:
        return len(text or "") < self.min_post_length
