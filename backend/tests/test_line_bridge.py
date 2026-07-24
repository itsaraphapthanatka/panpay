from .helpers import create_charge


def _post(client, api_key, **body):
    return client.post("/v1/line/transfer", headers={"Authorization": f"Bearer {api_key}"}, json=body)


def test_requires_api_key(client):
    assert client.post("/v1/line/transfer", json={"amount": 100, "message_id": "m1"}).status_code == 401


def test_matches_single_pending_charge(client, merchant, api_key):
    cid = create_charge(client, merchant["headers"], 321.0)["id"]
    r = _post(client, api_key, amount=321.0, message_id="msg-1", text="เงินเข้า 321.00 บาท", sender="LINE")
    assert r.status_code == 200, r.text
    assert r.json() == {"matched": True, "charge_id": cid, "amount": 321.0}
    # charge is now paid
    assert client.get(f"/v1/charges/{cid}", headers={"Authorization": f"Bearer {api_key}"}).json()["status"] == "paid"


def test_no_matching_amount(client, merchant, api_key):
    create_charge(client, merchant["headers"], 100.0)
    r = _post(client, api_key, amount=999.0, message_id="msg-2")
    assert r.json()["matched"] is False and r.json()["reason"] == "no_pending_charge"


def test_ambiguous_amount(client, merchant, api_key):
    create_charge(client, merchant["headers"], 50.0)
    create_charge(client, merchant["headers"], 50.0)
    r = _post(client, api_key, amount=50.0, message_id="msg-3")
    assert r.json()["matched"] is False and r.json()["reason"] == "ambiguous" and r.json()["count"] == 2


def test_idempotent_message(client, merchant, api_key):
    create_charge(client, merchant["headers"], 77.0)
    assert _post(client, api_key, amount=77.0, message_id="dup").json()["matched"] is True
    # same message_id again -> not reprocessed
    again = _post(client, api_key, amount=77.0, message_id="dup")
    assert again.json()["matched"] is False and again.json()["reason"] == "already_processed"


def test_matches_subscription_invoice_and_activates(client, merchant, api_key):
    H = merchant["headers"]
    plan = client.post("/dashboard/plans", headers=H, json={"name": "P", "amount": 199.0}).json()
    created = client.post("/dashboard/subscriptions", headers=H,
                          json={"plan_id": plan["id"], "customer_name": "A"}).json()
    r = _post(client, api_key, amount=199.0, message_id="sub-pay-1")
    assert r.json()["matched"] is True
    sub = client.get(f"/dashboard/subscriptions/{created['subscription']['id']}", headers=H).json()["subscription"]
    assert sub["status"] == "active"
