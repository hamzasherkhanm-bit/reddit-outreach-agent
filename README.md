# Reddit Outreach Agent

A scheduled Python pipeline that finds the Reddit (and Hacker News) posts most worth replying to for a given audience, ranks them, and delivers a short daily shortlist to Notion and email.

It is a research tool, not a bot. It never posts or comments; it only decides which conversations are worth a human's time.

## How it works

```
GitHub Actions cron (daily, 11:00 UTC)
  -> fetch      Reddit + Hacker News, last 24h, filtered by age / comment count
  -> prefilter  cheap yes/no relevance check with an LLM
  -> score      fit, urgency and value-add (0-10 each) plus a one-line reason
  -> deliver    top 15 to a Notion database, top 5 in an email digest (Resend)
```

Running cost is about $0.05/day in API calls. Reddit, GitHub Actions and Resend all run on free tiers.

## Project layout

| Path | Purpose |
|---|---|
| `config.yaml` | Subreddits, keywords, thresholds, models and audience profile |
| `prompts/` | Prefilter and scoring prompt templates |
| `src/main.py` | Pipeline entry point |
| `src/sources/` | Pluggable data sources (Reddit, Hacker News) |
| `src/prefilter.py`, `src/scorer.py` | Relevance check and scoring |
| `src/notion_sync.py`, `src/emailer.py` | Output to Notion and email |
| `tests/` | Offline end-to-end test with all external services faked |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

You will need:

- Reddit API credentials (script app at reddit.com/prefs/apps)
- An Anthropic API key
- A Notion integration token and a database shared with it
- A Resend API key and verified sender

The Notion columns are created and validated automatically on the first run.

## Running

```bash
python -m pytest tests/ -q   # offline test, no keys needed
python -m src.main           # real run
```

To deploy, add each `.env` variable as a GitHub Actions secret. The workflow in `.github/workflows/daily.yml` runs it every morning and can also be triggered manually from the Actions tab.

## Adapting it

Everything audience-specific lives in `config.yaml` (the `icp` section and the subreddit list) and the two prompt files, so the same pipeline can be pointed at a different niche without code changes. New platforms can be added under `src/sources/`; see `src/sources/ADDING_A_SOURCE.md`.
