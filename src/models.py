"""Shared data models for the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Post:
    """A candidate post from any source platform."""
    source: str            # "reddit" (future: other platforms)
    id: str                # platform-unique ID, used for dedupe
    title: str
    body: str
    url: str
    community: str         # e.g. subreddit name
    author: str
    created_utc: float
    num_comments: int
    score: int             # platform upvotes/likes
    op_context: str = ""   # OP's recent activity summary (improves value-add scoring)

    def age_hours(self, now_utc: float) -> float:
        return (now_utc - self.created_utc) / 3600.0


@dataclass
class ScoredPost:
    """A post plus the agent's judgment."""
    post: Post
    icp_fit: int = 0
    urgency: int = 0
    value_add: int = 0
    total: int = 0
    why: str = ""
    skip_reason: Optional[str] = None
    raw_response: str = field(default="", repr=False)  # kept for debugging

    def to_dict(self) -> dict:
        d = asdict(self.post)
        d.update(
            icp_fit=self.icp_fit, urgency=self.urgency, value_add=self.value_add,
            total=self.total, why=self.why, skip_reason=self.skip_reason,
        )
        return d
