"""Reddit fetcher - pulls recent posts from the watchlist via the official API (praw).

Filters: min comment count, max age, not removed/deleted.
Dedupe is by post ID across subreddits (crossposts appear once).
praw handles rate-limit backoff automatically.
"""
from __future__ import annotations

import time

import praw

from src.config import Settings
from src.models import Post
from src.sources.base import Source


class RedditSource(Source):
    name = "reddit"
    required_env = ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = settings.reddit
        self._reddit = praw.Reddit(
            client_id=settings.env("REDDIT_CLIENT_ID"),
            client_secret=settings.env("REDDIT_CLIENT_SECRET"),
            user_agent=settings.env("REDDIT_USER_AGENT"),
        )
        self._reddit.read_only = True

    def fetch(self) -> list[Post]:
        now = time.time()
        max_age_h = float(self.cfg.get("max_age_hours", 24))
        min_comments = int(self.cfg.get("min_comments", 5))
        cap = int(self.cfg.get("max_posts_per_subreddit", 50))

        seen: set[str] = set()
        posts: list[Post] = []

        for sub_name in self.cfg["subreddits"]:
            try:
                subreddit = self._reddit.subreddit(sub_name)
                for submission in subreddit.new(limit=cap):
                    post = self._to_post(submission, sub_name)
                    if post is None or post.id in seen:
                        continue
                    if post.age_hours(now) > max_age_h:
                        continue
                    if post.num_comments < min_comments:
                        continue
                    seen.add(post.id)
                    posts.append(post)
            except Exception as exc:  # one bad subreddit must not kill the run
                print(f"[reddit] WARNING: failed to fetch r/{sub_name}: {exc}")

        return posts

    @staticmethod
    def _to_post(submission, sub_name: str) -> Post | None:
        body = submission.selftext or ""
        if body in ("[removed]", "[deleted]"):
            return None
        if submission.removed_by_category is not None:
            return None
        author = str(submission.author) if submission.author else "[deleted]"
        if author == "[deleted]":
            return None
        return Post(
            source="reddit",
            id=submission.id,
            title=submission.title or "",
            body=body[:4000],  # keep token costs bounded
            url=f"https://www.reddit.com{submission.permalink}",
            community=sub_name,
            author=author,
            created_utc=float(submission.created_utc),
            num_comments=int(submission.num_comments or 0),
            score=int(submission.score or 0),
        )

    def enrich_op_context(self, post: Post, limit: int = 5) -> None:
        """Fetch the OP's recent activity - helps the scorer tell a real ICP
        from a throwaway account."""
        try:
            redditor = self._reddit.redditor(post.author)
            items = []
            for thing in redditor.new(limit=limit):
                kind = "post" if hasattr(thing, "title") else "comment"
                text = getattr(thing, "title", "") or getattr(thing, "body", "")
                sub = str(getattr(thing, "subreddit", ""))
                items.append(f"[{kind} in r/{sub}] {text[:150]}")
            post.op_context = "\n".join(items) if items else "(no recent activity found)"
        except Exception:
            post.op_context = "(could not fetch OP activity)"
