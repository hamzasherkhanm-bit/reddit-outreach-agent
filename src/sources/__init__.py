"""Source registry. main.py asks this module for all enabled sources."""
from __future__ import annotations

from src.config import Settings
from src.sources.base import Source
from src.sources.reddit_source import RedditSource
from src.sources.hn_source import HNSource

# To add a platform: import its class and add it here. That's the whole hookup.
_REGISTRY: dict[str, type[Source]] = {
    "reddit": RedditSource,
    "hackernews": HNSource,
}


def enabled_sources(settings: Settings) -> list[Source]:
    sources = []
    for name, cls in _REGISTRY.items():
        cfg = settings.cfg["sources"].get(name, {})
        if not (isinstance(cfg, dict) and cfg.get("enabled", False)):
            continue
        missing = [k for k in cls.required_env if not settings.env(k)]
        if missing:
            print(
                f"[sources] {name}: skipping this run - missing {', '.join(missing)}. "
                "Add them as GitHub Secrets and this source activates automatically."
            )
            continue
        sources.append(cls(settings))
    return sources
