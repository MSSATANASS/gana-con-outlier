"""Time-based email follow-up runner.

Once a day it walks every active lead and sends the next due email in the
sequence based on days elapsed since registration. Idempotent: a lead's
``last_email_day`` guards against re-sends. If a lead already advanced past a
stage, earlier emails are skipped (we only ever send the *latest* due step).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

import db
import emails

PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://gana-con-outlier.onrender.com")
SEQUENCE_DAYS = sorted(emails.SEQUENCE.keys())  # [0,2,5,10,20]


def _latest_due_day(days_elapsed: int, last_sent: int) -> int | None:
    """Highest sequence day that is <= days_elapsed and > last_sent."""
    candidates = [d for d in SEQUENCE_DAYS if d <= days_elapsed and d > last_sent]
    return max(candidates) if candidates else None


def run_followups() -> int:
    """Send due emails. Returns count sent. Safe to call repeatedly."""
    now = datetime.now(timezone.utc)
    sent = 0
    for lead in db.due_for_email(day=SEQUENCE_DAYS[-1] + 1):
        try:
            created = datetime.fromisoformat(lead["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            days_elapsed = (now - created).days
            due = _latest_due_day(days_elapsed, lead.get("last_email_day", -1))
            if due is None:
                continue
            ok = emails.send_stage_email(
                to=lead["email"], nombre=lead["nombre"], day=due,
                unsubscribe_url=f"{PUBLIC_URL}/unsubscribe?id={lead['id']}",
            )
            # Mark as processed even in dry-run so we don't loop forever.
            db.mark_email_sent(lead["id"], due)
            if ok:
                sent += 1
        except Exception as e:  # never let one bad lead kill the run
            print(f"[scheduler] error on lead {lead.get('id')}: {e}")
    print(f"[scheduler] followup run complete, sent={sent}")
    return sent


_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    # Daily at 15:00 UTC (~9am Mexico). Also run once shortly after boot.
    _scheduler.add_job(run_followups, "cron", hour=15, minute=0, id="daily_followups")
    _scheduler.start()
    print("[scheduler] started (daily 15:00 UTC)")
