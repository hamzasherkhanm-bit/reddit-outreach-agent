"""Writes the top N scored posts to a Notion database, and appends
plain-text run logs to a Notion page so runs can be debugged without reading code.

The DB schema lives in SCHEMA below (single source of truth).
ensure_schema() validates before writing and adds any missing properties.
"""
from __future__ import annotations

import datetime as dt

from notion_client import Client

from src.config import Settings
from src.models import ScoredPost

# Property name -> Notion property type. Title comes from the post title.
SCHEMA = {
    "Post": "title",
    "URL": "url",
    "Community": "select",
    "Source": "select",
    "Total": "number",
    "ICP fit": "number",
    "Urgency": "number",
    "Value-add": "number",
    "Why": "rich_text",
    "Comments": "number",
    "Posted": "date",
    "Run date": "date",
    "Status": "select",   # Manual workflow column: New / Commented / Skipped
}


class NotionSync:
    def __init__(self, settings: Settings):
        self.client = Client(auth=settings.env("NOTION_TOKEN"))
        self.database_id = settings.env("NOTION_DATABASE_ID")
        self.log_page_id = settings.env("NOTION_LOG_PAGE_ID")

    # --- schema ------------------------------------------------------------
    def ensure_schema(self) -> None:
        db = self.client.databases.retrieve(database_id=self.database_id)
        existing = db.get("properties", {})
        updates: dict = {}

        # Every DB has exactly one title property; rename it to "Post" if needed.
        title_name = next(
            (n for n, p in existing.items() if p.get("type") == "title"), None
        )
        if title_name and title_name != "Post":
            updates[title_name] = {"name": "Post"}

        for name, ptype in SCHEMA.items():
            if ptype != "title" and name not in existing:
                updates[name] = {ptype: {}}

        if updates:
            self.client.databases.update(database_id=self.database_id, properties=updates)
            # Verify the update actually took - fail loudly here, not mid-write.
            check = self.client.databases.retrieve(database_id=self.database_id)
            have = set(check.get("properties", {}))
            still_missing = [n for n in SCHEMA if n not in have]
            if still_missing:
                raise RuntimeError(
                    f"Notion DB is missing properties after schema update: {still_missing}. "
                    "Check that the integration has full access to the database."
                )

    # --- write -------------------------------------------------------------
    def write_posts(self, scored: list[ScoredPost]) -> int:
        run_date = dt.date.today().isoformat()
        written = 0
        for sp in scored:
            p = sp.post
            props = {
                "Post": {"title": [{"text": {"content": p.title[:200] or "(untitled)"}}]},
                "URL": {"url": p.url},
                "Community": {"select": {"name": p.community[:100]}},
                "Source": {"select": {"name": p.source}},
                "Total": {"number": sp.total},
                "ICP fit": {"number": sp.icp_fit},
                "Urgency": {"number": sp.urgency},
                "Value-add": {"number": sp.value_add},
                "Why": {"rich_text": [{"text": {"content": (sp.why or "")[:1900]}}]},
                "Comments": {"number": p.num_comments},
                "Posted": {"date": {"start": dt.datetime.fromtimestamp(
                    p.created_utc, tz=dt.timezone.utc).isoformat()}},
                "Run date": {"date": {"start": run_date}},
                "Status": {"select": {"name": "New"}},
            }
            self.client.pages.create(
                parent={"database_id": self.database_id}, properties=props
            )
            written += 1
        return written

    # --- logging -----------------------------------------------------------
    def append_log(self, lines: list[str]) -> None:
        """Append a plain-text log block to the Notion log page (best effort)."""
        if not self.log_page_id:
            return
        try:
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            text = f"── Run {stamp} ──\n" + "\n".join(lines)
            self.client.blocks.children.append(
                block_id=self.log_page_id,
                children=[{
                    "object": "block",
                    "type": "code",
                    "code": {
                        "language": "plain text",
                        "rich_text": [{"text": {"content": text[:1900]}}],
                    },
                }],
            )
        except Exception as exc:
            print(f"[notion] WARNING: could not write log page: {exc}")
