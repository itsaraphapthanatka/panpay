"""Scheduled jobs.

`run_due_renewals` processes every merchant: expires lapsed members, then issues
renewal invoices for memberships whose period has ended. Run it on a schedule:

    python -m app.jobs            # one-shot (use with system cron / k8s CronJob)

Or enable the in-process scheduler with RUN_SCHEDULER=true (single instance only).
"""

from sqlalchemy.orm import Session

from .config import settings
from .models import Merchant
from .subscription_ops import expire_lapsed, generate_due_invoices
from .webhooks import deliver_webhook, enqueue_subscription_event


def run_due_renewals(db: Session, grace_days: int | None = None) -> dict:
    grace = settings.subscription_grace_days if grace_days is None else grace_days
    renewals = 0
    expired = 0
    for merchant in db.query(Merchant).all():
        # Expire FIRST (so a membership just moved to past_due this run isn't expired immediately).
        for sub in expire_lapsed(db, merchant, grace):
            expired += 1
            delivery = enqueue_subscription_event(db, sub, merchant, "subscription.expired")
            if delivery:
                deliver_webhook(delivery.id, merchant.webhook_secret)  # sync in a batch job
        renewals += len(generate_due_invoices(db, merchant))
    return {"renewals": renewals, "expired": expired}


def main() -> None:
    from .database import SessionLocal

    db = SessionLocal()
    try:
        print(run_due_renewals(db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
