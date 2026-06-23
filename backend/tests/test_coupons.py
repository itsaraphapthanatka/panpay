from app.models import Coupon
from app.subscription_ops import apply_coupon

from .helpers import pay_charge


def test_apply_coupon_math():
    pct = Coupon(discount_type="percent", value=20, duration="once")
    fixed = Coupon(discount_type="fixed", value=50, duration="once")
    big = Coupon(discount_type="fixed", value=999, duration="once")
    assert apply_coupon(100.0, pct) == 80.0
    assert apply_coupon(100.0, fixed) == 50.0
    assert apply_coupon(100.0, big) == 0.0  # never negative


def _plan(client, H, amount=300.0):
    return client.post("/dashboard/plans", headers=H, json={"name": "P", "amount": amount}).json()


def _coupon(client, H, **over):
    body = {"code": "SAVE20", "discount_type": "percent", "value": 20, "duration": "once", **over}
    return client.post("/dashboard/coupons", headers=H, json=body)


def test_create_coupon_and_duplicate(client, merchant):
    H = merchant["headers"]
    assert _coupon(client, H).status_code == 201
    assert _coupon(client, H).status_code == 409  # duplicate code


def test_percent_over_100_rejected(client, merchant):
    assert _coupon(client, merchant["headers"], code="X", value=150).status_code == 400


def test_once_coupon_discounts_first_invoice_only(client, merchant):
    H = merchant["headers"]
    _coupon(client, H, code="ONCE20", value=20, duration="once")
    plan = _plan(client, H, 300.0)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": plan["id"], "customer_name": "A", "coupon_code": "ONCE20"}).json()
    assert created["invoice"]["amount"] == 240.0  # 20% off first
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])
    renewal = client.post(f"/dashboard/subscriptions/{sub_id}/invoice", headers=H).json()
    assert renewal["amount"] == 300.0  # full price on renewal


def test_forever_coupon_discounts_every_invoice(client, merchant):
    H = merchant["headers"]
    _coupon(client, H, code="FOREVER", discount_type="fixed", value=50, duration="forever")
    plan = _plan(client, H, 300.0)
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": plan["id"], "customer_name": "A", "coupon_code": "FOREVER"}).json()
    assert created["invoice"]["amount"] == 250.0
    sub_id = created["subscription"]["id"]
    pay_charge(client, created["invoice"]["id"])
    renewal = client.post(f"/dashboard/subscriptions/{sub_id}/invoice", headers=H).json()
    assert renewal["amount"] == 250.0  # still discounted


def test_invalid_and_exhausted_coupons(client, merchant):
    H = merchant["headers"]
    plan = _plan(client, H)
    # invalid code
    assert client.post("/dashboard/subscriptions", headers=H,
                       json={"plan_id": plan["id"], "customer_name": "A", "coupon_code": "NOPE"}).status_code == 400
    # max_redemptions = 1 -> second use rejected
    _coupon(client, H, code="ONE", max_redemptions=1)
    ok = client.post("/dashboard/subscriptions", headers=H,
                     json={"plan_id": plan["id"], "customer_name": "A", "coupon_code": "ONE"})
    assert ok.status_code == 201
    again = client.post("/dashboard/subscriptions", headers=H,
                        json={"plan_id": plan["id"], "customer_name": "B", "coupon_code": "ONE"})
    assert again.status_code == 400
    # redemption counter incremented
    coupons = {c["code"]: c for c in client.get("/dashboard/coupons", headers=H).json()}
    assert coupons["ONE"]["times_redeemed"] == 1
