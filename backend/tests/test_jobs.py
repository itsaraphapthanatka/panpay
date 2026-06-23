from datetime import datetime, timezone

from app.database import SessionLocal
from app.jobs import run_due_renewals
from app.models import Subscription

from .helpers import pay_charge


class _Resp:
    status_code = 200
    content = b""


def _active_member(client, headers):
    p = client.post("/dashboard/plans", headers=headers,
                    json={"name": "M", "amount": 100, "interval_unit": "month", "interval_count": 1}).json()
    created = client.post("/dashboard/subscriptions", headers=headers,
                          json={"plan_id": p["id"], "customer_name": "A"}).json()
    pay_charge(client, created["invoice"]["id"])
    return created["subscription"]["id"]


def _force_period_end(sub_id, dt):
    db = SessionLocal()
    try:
        s = db.get(Subscription, sub_id)
        s.current_period_end = dt
        db.commit()
    finally:
        db.close()


def test_job_issues_renewal_for_ended_period(client, merchant):
    H = merchant["headers"]
    sub_id = _active_member(client, H)
    _force_period_end(sub_id, datetime(2020, 1, 1, tzinfo=timezone.utc))
    db = SessionLocal()
    try:
        summary = run_due_renewals(db, grace_days=3)
    finally:
        db.close()
    assert summary["renewals"] == 1
    assert client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]["status"] == "past_due"


def test_job_expires_lapsed_and_fires_webhook(client, merchant, monkeypatch):
    import app.webhooks as wh

    events = []
    monkeypatch.setattr(wh.httpx, "post",
                        lambda url, content=None, headers=None, timeout=None: events.append(headers["X-Panpay-Event"]) or _Resp())

    H = merchant["headers"]
    client.patch("/dashboard/settings", headers=H, json={"webhook_url": "https://shop.example/wh"})
    sub_id = _active_member(client, H)
    _force_period_end(sub_id, datetime(2020, 1, 1, tzinfo=timezone.utc))

    db = SessionLocal()
    try:
        run_due_renewals(db, grace_days=3)        # run 1: active+ended -> renewal -> past_due
        summary = run_due_renewals(db, grace_days=3)  # run 2: past_due lapsed -> expired
    finally:
        db.close()

    assert summary["expired"] == 1
    assert client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]["status"] == "expired"
    assert "subscription.expired" in events


def test_job_noop_when_nothing_due(client, merchant):
    db = SessionLocal()
    try:
        assert run_due_renewals(db) == {"renewals": 0, "expired": 0}
    finally:
        db.close()
