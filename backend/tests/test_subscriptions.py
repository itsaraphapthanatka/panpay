from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Subscription
from app.subscription_ops import add_interval

from .helpers import pay_charge


# ---- interval math (unit) ----
def test_add_interval_month_clamps_end_of_month():
    d = datetime(2024, 1, 31, tzinfo=timezone.utc)
    assert add_interval(d, "month", 1) == datetime(2024, 2, 29, tzinfo=timezone.utc)  # leap
    assert add_interval(datetime(2023, 1, 31, tzinfo=timezone.utc), "month", 1).day == 28


def test_add_interval_year_and_day():
    assert add_interval(datetime(2024, 2, 29, tzinfo=timezone.utc), "year", 1) == datetime(2025, 2, 28, tzinfo=timezone.utc)
    assert add_interval(datetime(2024, 1, 1, tzinfo=timezone.utc), "day", 30) == datetime(2024, 1, 31, tzinfo=timezone.utc)


# ---- plans ----
def _plan(client, headers, **over):
    body = {"name": "Gold", "amount": 299.0, "interval_unit": "month", "interval_count": 1, **over}
    r = client.post("/dashboard/plans", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list_plans(client, merchant):
    p = _plan(client, merchant["headers"])
    assert p["active"] is True and p["amount"] == 299.0
    plans = client.get("/dashboard/plans", headers=merchant["headers"]).json()
    assert any(x["id"] == p["id"] for x in plans)


def test_cannot_delete_plan_in_use(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    client.post("/dashboard/subscriptions", headers=H, json={"plan_id": p["id"], "customer_name": "A"})
    assert client.delete(f"/dashboard/plans/{p['id']}", headers=H).status_code == 409


# ---- subscriptions ----
def test_create_subscription_issues_pending_invoice(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    r = client.post("/dashboard/subscriptions", headers=H,
                    json={"plan_id": p["id"], "customer_name": "สมชาย", "customer_email": "s@x.io"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["subscription"]["status"] == "pending"
    assert body["subscription"]["plan_name"] == "Gold"
    assert body["invoice"]["status"] == "pending"
    assert body["invoice"]["amount"] == 299.0
    assert body["invoice"]["checkout_url"].endswith(f"/pay/{body['invoice']['id']}")


def test_paying_invoice_activates_membership(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": p["id"], "customer_name": "A"}).json()
    sub_id = created["subscription"]["id"]
    assert pay_charge(client, created["invoice"]["id"]).status_code == 200

    sub = client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]
    assert sub["status"] == "active"
    assert sub["current_period_start"] and sub["current_period_end"]
    assert sub["current_period_end"] > sub["current_period_start"]


def test_renewal_then_payment_extends_period(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": p["id"], "customer_name": "A"}).json()
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])
    end1 = client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]["current_period_end"]

    # issue a renewal invoice -> past_due, then pay it -> active + later period end
    inv2 = client.post(f"/dashboard/subscriptions/{sub_id}/invoice", headers=H).json()
    assert client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]["status"] == "past_due"
    pay_charge(client, inv2["id"])
    sub = client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]
    assert sub["status"] == "active"
    assert sub["current_period_end"] > end1  # extended


def test_cancel_subscription(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    sub_id = client.post("/dashboard/subscriptions", headers=H,
                         json={"plan_id": p["id"], "customer_name": "A"}).json()["subscription"]["id"]
    r = client.post(f"/dashboard/subscriptions/{sub_id}/cancel", headers=H)
    assert r.status_code == 200 and r.json()["status"] == "canceled" and r.json()["canceled_at"]
    assert client.post(f"/dashboard/subscriptions/{sub_id}/cancel", headers=H).status_code == 409
    assert client.post(f"/dashboard/subscriptions/{sub_id}/invoice", headers=H).status_code == 409


class _Resp:
    status_code = 200
    content = b""


def test_subscription_webhook_events(client, merchant, monkeypatch):
    import app.webhooks as wh

    events = []
    monkeypatch.setattr(wh.httpx, "post",
                        lambda url, content=None, headers=None, timeout=None: events.append(headers["X-Panpay-Event"]) or _Resp())

    H = merchant["headers"]
    client.patch("/dashboard/settings", headers=H, json={"webhook_url": "https://shop.example/wh"})
    p = _plan(client, H)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": p["id"], "customer_name": "A"}).json()
    sub_id = created["subscription"]["id"]

    pay_charge(client, created["invoice"]["id"])                 # subscription.activated
    inv2 = client.post(f"/dashboard/subscriptions/{sub_id}/invoice", headers=H).json()
    pay_charge(client, inv2["id"])                                # subscription.renewed
    client.post(f"/dashboard/subscriptions/{sub_id}/cancel", headers=H)  # subscription.canceled

    assert "subscription.activated" in events
    assert "subscription.renewed" in events
    assert "subscription.canceled" in events


def test_generate_due_invoices(client, merchant):
    H = merchant["headers"]
    p = _plan(client, H)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": p["id"], "customer_name": "A"}).json()
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])

    # force the period to have ended
    db = SessionLocal()
    try:
        sub = db.get(Subscription, sub_id)
        sub.current_period_end = datetime(2020, 1, 1, tzinfo=timezone.utc)
        db.commit()
    finally:
        db.close()

    invoices = client.post("/dashboard/subscriptions/generate-due", headers=H).json()
    assert len(invoices) == 1
    assert invoices[0]["status"] == "pending"
    # second run issues nothing new (open invoice exists)
    assert client.post("/dashboard/subscriptions/generate-due", headers=H).json() == []
