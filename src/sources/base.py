"""Source interface. Every platform fetcher implements this.

To add a platform, subclass Source, implement fetch(), and register it in
src/sources/__init__.py. See ADDING_A_SOURCE.md in this folder - and read
the ToS note there before writing any new fetcher.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.models import Post


class Source(ABC):
    name: str = "base"
    # Env vars this source needs. If any are missing at runtime, the source is
    # skipped with a warning instead of crashing the whole run - so a source
    # whose credentials are still pending "switches on" the day they're added.
    required_env: list[str] = []

    @abstractmethod
    def fetch(self) -> list[Post]:
        """Return candidate posts from the last window, already filtered."""
        raise NotImplementedError
