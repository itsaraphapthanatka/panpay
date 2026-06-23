from datetime import timedelta

from app.database import SessionLocal
from app.models import Charge, utcnow


def test_create_charge_via_api_key(client, api_key):
    r = client.post("/v1/charges", headers={"Authorization": f"Bearer {api_key}"},
                    json={"amount": 100.0, "reference": "order-1", "description": "Coffee"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["amount"] == 100.0
    assert body["checkout_url"].endswith(f"/pay/{body['id']}")


def test_create_charge_via_dashboard(client, merchant):
    r = client.post("/dashboard/charges", headers=merchant["headers"], json={"amount": 250.5})
    assert r.status_code == 201
    assert r.json()["amount"] == 250.5


def test_api_requires_valid_key(client):
    assert client.post("/v1/charges", headers={"Authorization": "Bearer sk_live_bogus"},
                       json={"amount": 1}).status_code == 401
    assert client.post("/v1/charges", json={"amount": 1}).status_code == 401


def test_create_without_promptpay_fails(client):
    # merchant with no promptpay_id and no accounts
    import secrets
    email = f"np_{secrets.token_hex(4)}@panpay.io"
    tok = client.post("/auth/register", json={
        "email": email, "password": "secret123", "business_name": "NoPP",
    }).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}
    assert client.post("/dashboard/charges", headers=H, json={"amount": 50}).status_code == 400


def test_get_and_list_charges(client, api_key):
    H = {"Authorization": f"Bearer {api_key}"}
    cid = client.post("/v1/charges", headers=H, json={"amount": 10}).json()["id"]
    assert client.get(f"/v1/charges/{cid}", headers=H).json()["id"] == cid
    listed = client.get("/v1/charges", headers=H).json()
    assert any(c["id"] == cid for c in listed)
    assert client.get("/v1/charges/chg_missing", headers=H).status_code == 404


def test_amount_must_be_positive(client, api_key):
    r = client.post("/v1/charges", headers={"Authorization": f"Bearer {api_key}"}, json={"amount": 0})
    assert r.status_code == 422


def test_expired_charge_transitions_on_read(client, merchant):
    cid = client.post("/dashboard/charges", headers=merchant["headers"],
                      json={"amount": 30, "expires_in": 3600}).json()["id"]
    # force expiry in the past
    db = SessionLocal()
    try:
        ch = db.get(Charge, cid)
        ch.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    r = client.get(f"/checkout/{cid}")
    assert r.json()["status"] == "expired"
