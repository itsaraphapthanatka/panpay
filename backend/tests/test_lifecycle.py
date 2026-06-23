from .helpers import create_charge, pay_charge


def test_void_pending_charge(client, merchant):
    cid = create_charge(client, merchant["headers"], 80.0)["id"]
    r = client.post(f"/dashboard/charges/{cid}/void", headers=merchant["headers"])
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"
    assert r.json()["canceled_at"]
    # cannot void twice
    assert client.post(f"/dashboard/charges/{cid}/void", headers=merchant["headers"]).status_code == 409


def test_cannot_void_paid(client, merchant):
    cid = create_charge(client, merchant["headers"], 80.0)["id"]
    pay_charge(client, cid)
    assert client.post(f"/dashboard/charges/{cid}/void", headers=merchant["headers"]).status_code == 409


def test_refund_paid_charge(client, merchant):
    cid = create_charge(client, merchant["headers"], 120.0)["id"]
    pay_charge(client, cid)
    r = client.post(f"/dashboard/charges/{cid}/refund", headers=merchant["headers"], json={"reason": "ลูกค้าขอคืน"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "refunded"
    assert body["refunded_at"] and body["refund_reason"] == "ลูกค้าขอคืน"
    # cannot refund twice
    assert client.post(f"/dashboard/charges/{cid}/refund", headers=merchant["headers"], json={}).status_code == 409


def test_cannot_refund_pending(client, merchant):
    cid = create_charge(client, merchant["headers"], 5.0)["id"]
    assert client.post(f"/dashboard/charges/{cid}/refund", headers=merchant["headers"], json={}).status_code == 409


def test_void_refund_via_api_key(client, api_key):
    H = {"Authorization": f"Bearer {api_key}"}
    cid = client.post("/v1/charges", headers=H, json={"amount": 40}).json()["id"]
    assert client.post(f"/v1/charges/{cid}/void", headers=H).json()["status"] == "canceled"
