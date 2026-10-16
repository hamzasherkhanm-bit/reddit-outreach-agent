"""Sends the 7am digest via Resend, plus failure/zero-post alerts.

Digest emails (the digest and the friendly no-posts note) go to EMAIL_TO.
Operational alerts with raw pipeline logs go to ALERT_EMAIL_TO (the
maintainer) so recipients never see internals like [fetch]/[scorer] lines.
"""
from __future__ import annotations

import datetime as dt
import html

import resend

from src.config import Settings
from src.models import ScoredPost


def _post_block(rank: int, sp: ScoredPost) -> str:
    p = sp.post
    title = html.escape(p.title)
    why = html.escape(sp.why or "")
    return f"""
<div style="margin-bottom:20px;padding:14px 16px;border:1px solid #e2e2e2;border-radius:8px;">
  <div style="font-size:15px;font-weight:600;margin-bottom:4px;">
    {rank}. <a href="{p.url}" style="color:#1a4fd6;text-decoration:none;">{title}</a>
  </div>
  <div style="font-size:12px;color:#666;margin-bottom:6px;">
    r/{html.escape(p.community)} · {p.num_comments} comments ·
    score {sp.total}/30 (ICP {sp.icp_fit} · urgency {sp.urgency} · value {sp.value_add})
  </div>
  <div style="font-size:13px;color:#333;">{why}</div>
</div>"""


def send_digest(scored_top: list[ScoredPost], settings: Settings) -> None:
    resend.api_key = settings.env("RESEND_API_KEY")
    today = dt.date.today().strftime("%A, %b %-d")
    blocks = "".join(_post_block(i + 1, sp) for i, sp in enumerate(scored_top))
    body = f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:640px;margin:0 auto;">
  <h2 style="font-size:18px;">Your top {len(scored_top)} posts - {today}</h2>
  {blocks}
  <p style="font-size:12px;color:#888;">
    The full ranked list (with reasoning) is in your Notion database.
  </p>
</div>"""
    resend.Emails.send({
        "from": settings.env("EMAIL_FROM"),
        "to": [settings.env("EMAIL_TO")],
        "subject": f"{settings.output['email_subject_prefix']} - {today}",
        "html": body,
    })


def send_no_posts_note(posts_reviewed: int, settings: Settings) -> None:
    """Friendly recipient-facing note for days when nothing qualified.

    Replaces the old behavior of sending the raw-log alert to the recipient.
    """
    resend.api_key = settings.env("RESEND_API_KEY")
    today = dt.date.today().strftime("%A, %b %-d")
    body = f"""
<div style="font-family:-apple-system,Segoe UI,sans-serif;max-width:640px;margin:0 auto;">
  <h2 style="font-size:18px;">No qualifying posts today - {today}</h2>
  <p style="font-size:14px;color:#333;">
    The agent reviewed {posts_reviewed} posts this morning, but none were a
    close enough match to your audience to be worth your time today.
    Your next digest will arrive the morning there's a genuine match -
    quality over volume.
  </p>
  <p style="font-size:12px;color:#888;">
    Post volume will increase significantly once Reddit's career communities
    come online (approval pending on Reddit's side).
  </p>
</div>"""
    resend.Emails.send({
        "from": settings.env("EMAIL_FROM"),
        "to": [settings.env("EMAIL_TO")],
        "subject": f"{settings.output['email_subject_prefix']} - no qualifying posts today",
        "html": body,
    })


def send_alert(subject: str, message: str, settings: Settings) -> None:
    """Operational alert (raw logs) - goes to the maintainer, never the recipient."""
    try:
        resend.api_key = settings.env("RESEND_API_KEY")
        to = settings.env("ALERT_EMAIL_TO") or settings.env("EMAIL_TO")
        resend.Emails.send({
            "from": settings.env("EMAIL_FROM"),
            "to": [to],
            "subject": f"[agent alert] {subject}",
            "html": f"<pre style='font-family:monospace'>{html.escape(message)}</pre>",
        })
    except Exception as exc:
        print(f"[emailer] WARNING: alert email failed too: {exc}")
