from app.database import SessionLocal
from app.models import Subscription

from .helpers import pay_charge


def _plan(client, H, name, amount, unit="month"):
    return client.post("/dashboard/plans", headers=H,
                       json={"name": name, "amount": amount, "interval_unit": unit, "interval_count": 1}).json()


def _subscribe(client, H, plan_id, name="A"):
    return client.post("/dashboard/subscriptions", headers=H,
                       json={"plan_id": plan_id, "customer_name": name}).json()


def test_pending_change_reissues_at_new_price(client, merchant):
    H = merchant["headers"]
    cheap = _plan(client, H, "Cheap", 100)
    pricey = _plan(client, H, "Pricey", 500)
    created = _subscribe(client, H, cheap["id"])
    sub_id = created["subscription"]["id"]

    detail = client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                         json={"plan_id": pricey["id"]}).json()
    assert detail["subscription"]["plan_id"] == pricey["id"]
    # the old pending invoice is canceled and a new full-price one issued
    open_invoices = [c for c in detail["invoices"] if c["status"] == "pending"]
    assert len(open_invoices) == 1 and open_invoices[0]["amount"] == 500.0


def test_upgrade_active_prorates_a_positive_difference(client, merchant):
    H = merchant["headers"]
    cheap = _plan(client, H, "Cheap", 100)
    pricey = _plan(client, H, "Pricey", 500)
    created = _subscribe(client, H, cheap["id"])
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])  # active, ~full month remaining

    detail = client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                         json={"plan_id": pricey["id"]}).json()
    assert detail["subscription"]["plan_id"] == pricey["id"]
    proration = [c for c in detail["invoices"] if (c.get("metadata") or {}).get("proration")]
    assert len(proration) == 1
    # nearly a full month remains -> close to the 400 difference
    assert 300 < proration[0]["amount"] <= 400


def test_paying_proration_does_not_extend_period(client, merchant):
    H = merchant["headers"]
    cheap = _plan(client, H, "Cheap", 100)
    pricey = _plan(client, H, "Pricey", 500)
    created = _subscribe(client, H, cheap["id"])
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])
    end_before = client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]["current_period_end"]

    detail = client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                         json={"plan_id": pricey["id"]}).json()
    proration = [c for c in detail["invoices"] if (c.get("metadata") or {}).get("proration")][0]
    pay_charge(client, proration["id"])

    end_after = client.get(f"/dashboard/subscriptions/{sub_id}", headers=H).json()["subscription"]
    assert end_after["status"] == "active"
    assert end_after["current_period_end"] == end_before  # proration must not extend


def test_downgrade_active_no_charge(client, merchant):
    H = merchant["headers"]
    pricey = _plan(client, H, "Pricey", 500)
    cheap = _plan(client, H, "Cheap", 100)
    created = _subscribe(client, H, pricey["id"])
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])

    detail = client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                         json={"plan_id": cheap["id"]}).json()
    assert detail["subscription"]["plan_id"] == cheap["id"]
    assert [c for c in detail["invoices"] if (c.get("metadata") or {}).get("proration")] == []


def test_change_plan_guards(client, merchant):
    H = merchant["headers"]
    p1 = _plan(client, H, "P1", 100)
    created = _subscribe(client, H, p1["id"])
    sub_id = created["subscription"]["id"]
    # same plan
    assert client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                       json={"plan_id": p1["id"]}).status_code == 400
    # canceled
    client.post(f"/dashboard/subscriptions/{sub_id}/cancel", headers=H)
    p2 = _plan(client, H, "P2", 200)
    assert client.post(f"/dashboard/subscriptions/{sub_id}/change-plan", headers=H,
                       json={"plan_id": p2["id"]}).status_code == 409
