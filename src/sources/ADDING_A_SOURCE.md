# Adding a new platform source

The pipeline is platform-agnostic past the fetch step: anything that returns
`list[Post]` flows through pre-filter → scorer → Notion → email unchanged.

## How

1. Create `src/sources/<platform>_source.py` with a class that subclasses
   `Source` and implements `fetch() -> list[Post]`.
2. Register it in `src/sources/__init__.py` (`_REGISTRY`).
3. Add a config block under `sources:` in `config.yaml` with `enabled: true`.

That's it - no changes anywhere else.

## Why Instagram / TikTok / LinkedIn are not implemented

This was considered and deliberately rejected, not forgotten:

- **LinkedIn** has no API for searching or reading other people's posts.
  Scraping is explicitly prohibited by its User Agreement, and LinkedIn
  actively bans accounts that do it. Losing the LinkedIn account
  would damage the exact channel this project is meant to grow.
- **Instagram**'s Graph API only exposes your own business account's media
  plus a very limited hashtag endpoint. There is no permitted way to
  discover strangers' posts about layoffs.
- **TikTok**'s Research API is restricted to vetted academic institutions.

If a platform ships a permitted API for this later, the interface above is
where it plugs in. Until then, Reddit is the only platform where this agent
can operate both effectively and within the rules - which is why v1
focuses on Reddit.
