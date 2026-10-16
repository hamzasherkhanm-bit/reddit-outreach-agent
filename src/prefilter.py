"""Cheap binary pass: 'is this even tech-career?' Drops obvious noise before
the more expensive scoring call."""
from __future__ import annotations

import time

from src.config import Settings
from src.llm import LLM
from src.models import Post


def prefilter(posts: list[Post], settings: Settings, llm: LLM) -> list[Post]:
    template = settings.prompt("prefilter")
    model = settings.scoring["prefilter_model"]
    survivors: list[Post] = []

    for post in posts:
        prompt = template.format(
            business=settings.icp["business"],
            title=post.title,
            subreddit=post.community,
            body=post.body[:1500] or "(no body text)",
        )
        try:
            answer = llm.complete(model, prompt, max_tokens=5).upper()
        except Exception as exc:
            # If the filter itself fails, keep the post - the scorer decides.
            print(f"[prefilter] WARNING on {post.id}: {exc}; keeping post")
            survivors.append(post)
            continue
        if answer.startswith("Y"):
            survivors.append(post)

    return survivors
