"""Hacker News fetcher - uses the official, open Algolia search API (no key needed).

Why HN: its "Ask HN" stories regularly include layoff / job-search / career
posts that match the ICP, and unlike Instagram/TikTok/LinkedIn the API is
public and explicitly free to use. See ADDING_A_SOURCE.md.
"""
from __future__ import annotations

import time

import requests

from src.config import Settings
from src.models import Post
from src.sources.base import Source

API = "https://hn.algolia.com/api/v1/search_by_date"

_HTML_REPLACEMENTS = (
    ("<p>", "\n"), ("</p>", ""),
    ("&#x27;", "'"), ("&quot;", '"'),
    ("&gt;", ">"), ("&lt;", "<"), ("&amp;", "&"),
)


class HNSource(Source):
    name = "hackernews"
    required_env: list[str] = []  # open API - no credentials

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cfg = settings.cfg["sources"]["hackernews"]

    def fetch(self) -> list[Post]:
        now = time.time()
        max_age_h = float(self.cfg.get("max_age_hours", 24))
        min_comments = int(self.cfg.get("min_comments", 2))
        cap = int(self.cfg.get("max_posts_per_search", 100))
        cutoff = int(now - max_age_h * 3600)

        # Ask HN firehose + one keyword search per configured keyword
        searches: list[tuple[str, str | None]] = [("ask_hn", None)]
        for kw in self.cfg.get("keywords", []):
            searches.append(("story", kw))

        seen: set[str] = set()
        posts: list[Post] = []

        for tags, query in searches:
            try:
                params = {
                    "tags": tags,
                    "numericFilters": f"created_at_i>{cutoff}",
                    "hitsPerPage": cap,
                    # exact matching only - stops fuzzy hits like "paid off" ~ "laid off"
                    "typoTolerance": "false",
                }
                if query:
                    # quote multi-word keywords so they match as exact phrases
                    params["query"] = f'"{query}"' if " " in query else query
                    params["advancedSyntax"] = "true"
                resp = requests.get(API, params=params, timeout=30)
                resp.raise_for_status()
                for hit in resp.json().get("hits", []):
                    post = self._to_post(hit)
                    if post is None or post.id in seen:
                        continue
                    if post.num_comments < min_comments:
                        continue
                    seen.add(post.id)
                    posts.append(post)
            except Exception as exc:  # one bad search must not kill the run
                print(f"[hackernews] WARNING: search failed ({tags}/{query}): {exc}")

        return posts

    @staticmethod
    def _to_post(hit: dict) -> Post | None:
        object_id = str(hit.get("objectID", ""))
        title = hit.get("title") or ""
        if not object_id or not title:
            return None
        body = hit.get("story_text") or ""
        for old, new in _HTML_REPLACEMENTS:
            body = body.replace(old, new)
        return Post(
            source="hackernews",
            id=f"hn_{object_id}",
            title=title,
            body=body[:4000],  # keep token costs bounded
            url=f"https://news.ycombinator.com/item?id={object_id}",
            community="Ask HN" if "ask_hn" in (hit.get("_tags") or []) else "Hacker News",
            author=hit.get("author") or "unknown",
            created_utc=float(hit.get("created_at_i") or 0),
            num_comments=int(hit.get("num_comments") or 0),
            score=int(hit.get("points") or 0),
        )
