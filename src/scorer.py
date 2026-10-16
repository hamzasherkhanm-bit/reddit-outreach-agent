"""Full ICP scoring pass. Returns ScoredPost with reasoning for every candidate.

JSON is validated and clamped; a malformed model response never crashes the run -
the post just gets total=0 with a skip_reason so it's visible in the logs.
"""
from __future__ import annotations

import json
import re
import time

from src.config import Settings
from src.llm import LLM
from src.models import Post, ScoredPost


def _time_ago(post: Post, now: float) -> str:
    hours = post.age_hours(now)
    return f"{int(hours * 60)} minutes ago" if hours < 1 else f"{hours:.0f} hours ago"


def _parse_json(text: str) -> dict:
    """Extract the first JSON object from the model output."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in model response")
    return json.loads(match.group(0))


def _clamp(value, lo=0, hi=10) -> int:
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return 0


def score_posts(posts: list[Post], settings: Settings, llm: LLM) -> list[ScoredPost]:
    template = settings.prompt("scorer")
    model = settings.scoring["scorer_model"]
    skip_threshold = int(settings.scoring["skip_threshold"])
    now = time.time()
    scored: list[ScoredPost] = []

    for post in posts:
        prompt = template.format(
            business=settings.icp["business"],
            icp_profile=settings.icp["profile"].strip(),
            skip_threshold=skip_threshold,
            title=post.title,
            subreddit=post.community,
            time_ago=_time_ago(post, now),
            num_comments=post.num_comments,
            op_context=post.op_context or "(not available)",
            body=post.body[:3000] or "(no body text)",
        )
        sp = ScoredPost(post=post)
        try:
            raw = llm.complete(model, prompt, max_tokens=400)
            sp.raw_response = raw
            data = _parse_json(raw)
            sp.icp_fit = _clamp(data.get("icp_fit"))
            sp.urgency = _clamp(data.get("urgency"))
            sp.value_add = _clamp(data.get("value_add"))
            sp.total = sp.icp_fit + sp.urgency + sp.value_add  # recompute, don't trust the model's sum
            sp.why = str(data.get("why", ""))[:500]
            sp.skip_reason = data.get("skip_reason") if sp.total < skip_threshold else None
            if sp.total < skip_threshold and not sp.skip_reason:
                sp.skip_reason = "below threshold"
        except Exception as exc:
            sp.skip_reason = f"scoring failed: {exc}"
            print(f"[scorer] WARNING on {post.id}: {exc}")
        scored.append(sp)

    scored.sort(key=lambda s: s.total, reverse=True)
    return scored
