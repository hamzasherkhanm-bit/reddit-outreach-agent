"""Pipeline orchestrator. Run with: python -m src.main

Flow: fetch → pre-filter → score → Notion (top 15) + email (top 5).
Every stage logs counts; logs also land on the Notion log page.
"""
from __future__ import annotations

import sys
import traceback

from src.config import Settings
from src.llm import LLM
from src.sources import enabled_sources
from src.prefilter import prefilter
from src.scorer import score_posts
from src.notion_sync import NotionSync
from src.emailer import send_digest, send_alert, send_no_posts_note


def run(settings: Settings) -> None:
    log: list[str] = []

    def note(msg: str) -> None:
        print(msg)
        log.append(msg)

    llm = LLM(settings.env("ANTHROPIC_API_KEY"))
    notion = NotionSync(settings)

    # 1. Fetch ---------------------------------------------------------------
    posts = []
    for source in enabled_sources(settings):
        fetched = source.fetch()
        note(f"[fetch] {source.name}: {len(fetched)} candidate posts")
        posts.extend(fetched)

    if not posts:
        note("[fetch] zero posts - alerting")
        send_alert("Zero posts fetched", "\n".join(log), settings)
        notion.append_log(log)
        return

    # 2. Pre-filter ----------------------------------------------------------
    survivors = prefilter(posts, settings, llm)
    note(f"[prefilter] {len(posts)} → {len(survivors)} posts")

    # Cost guardrail
    cap = int(settings.scoring.get("max_scored_per_run", 120))
    if len(survivors) > cap:
        survivors.sort(key=lambda p: p.num_comments, reverse=True)
        survivors = survivors[:cap]
        note(f"[prefilter] capped to {cap} most-active posts")

    # 3. Enrich OP context for scoring (reddit only) --------------------------
    for source in enabled_sources(settings):
        if hasattr(source, "enrich_op_context"):
            for post in survivors:
                if post.source == source.name:
                    source.enrich_op_context(post)

    # 4. Score ----------------------------------------------------------------
    scored = score_posts(survivors, settings, llm)
    qualified = [s for s in scored if s.skip_reason is None]
    note(f"[scorer] {len(scored)} scored, {len(qualified)} above threshold")

    # 5. Deliver ----------------------------------------------------------------
    # Quality floor: posts below notion_min_total never reach the board.
    floor = int(settings.output.get("notion_min_total", 0))
    board_worthy = [s for s in scored if s.total >= floor]
    note(f"[notion] {len(board_worthy)} posts above board floor ({floor})")
    top_notion = board_worthy[: int(settings.output["notion_top_n"])]
    # Board-worthy means email-worthy: if a post is good enough for the Notion
    # board, it goes in the digest too. (Previously the email used the stricter
    # skip_threshold, so board posts could silently miss the email.)
    top_email = top_notion[: int(settings.output["email_top_n"])]

    notion.ensure_schema()
    written = notion.write_posts(top_notion)
    note(f"[notion] wrote {written} rows")

    if top_email:
        send_digest(top_email, settings)
        note(f"[email] digest sent with {len(top_email)} posts")
    else:
        # Recipient gets a friendly note; raw logs go to the maintainer only.
        send_no_posts_note(len(posts), settings)
        send_alert("No qualified posts today",
                   "The run worked but nothing beat the threshold.\n\n" + "\n".join(log),
                   settings)
        note("[email] no qualified posts - recipient note + maintainer alert sent")

    notion.append_log(log)
    note("[done] run complete")


def main() -> int:
    try:
        settings = Settings()
    except Exception as exc:
        print(f"FATAL: {exc}")
        return 1
    try:
        run(settings)
        return 0
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        try:
            send_alert("Pipeline crashed", tb, settings)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
