"""Quick sanity check for Reddit credentials and configuration.

Run from backend/ root::

    python -m scripts.reddit_test                # auth + fetch dry run
    python -m scripts.reddit_test --reply <id> "<text>"   # post a real reply

The dry-run mode never writes anything to Reddit; it only verifies that the
credentials work, the configured subreddits are reachable, and the ticker
filter would pick up matching submissions in the latest listing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from botvmar.adapters.reddit.adapter import RedditAdapter
from botvmar.config.platforms import load_one
from botvmar.db.pool import close_pool, init_pool
from botvmar.utils.logger import get_logger

logger = get_logger("scripts.reddit_test")


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Reddit adapter sanity check")
    parser.add_argument(
        "--reply", nargs=2, metavar=("SUBMISSION_ID", "TEXT"),
        help="Post a real reply under the given submission id (USE WITH CARE)",
    )
    parser.add_argument(
        "--ticker", default=None,
        help="Override the ticker for the dry-run fetch (defaults to platform_settings.ticker)",
    )
    args = parser.parse_args(argv)

    await init_pool()
    try:
        cfg = await load_one("reddit")
        if cfg is None:
            print("ERROR: no platform_settings row for 'reddit' — run prisma db seed first")
            return 2
        ticker = args.ticker or cfg.ticker

        adapter = RedditAdapter(config=cfg)
        await adapter.init()
        print(f"✓ Logged in to Reddit as the configured user")
        print(f"✓ Subreddits configured: {cfg.config.get('subreddits') or '<none>'}")
        print(f"✓ Search keywords: {cfg.config.get('searchQueries') or '<none>'}")
        print(f"  Ticker: {ticker}")
        print()

        if args.reply:
            sub_id, text = args.reply
            from botvmar.adapters.base import Post
            fake_post = Post(
                id=f"reddit_t3_{sub_id}",
                platform="reddit",
                author="manual_test",
                text="(manual test trigger)",
                raw={"submission_id": sub_id, "subreddit": "manual"},
            )
            ok = await adapter.reply_to(fake_post, text)
            print(f"reply_to({sub_id!r}): {'OK' if ok else 'FAILED'}")
        else:
            posts = await adapter.fetch_posts(ticker)
            print(f"✓ {len(posts)} matching submission(s) found:")
            for p in posts[:10]:
                print(f"  - r/{p.raw.get('subreddit')} [{p.author}] {p.id}")
                print(f"      {(p.raw.get('title') or '')[:120]}")
                print(f"      {p.url}")

        await adapter.cleanup()
        return 0
    finally:
        await close_pool()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
