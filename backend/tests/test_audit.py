from .helpers import create_charge, pay_charge


def test_actions_are_audited(client, merchant, api_key):
    H = merchant["headers"]
    cid = create_charge(client, H, 100.0)["id"]
    pay_charge(client, cid)
    client.post(f"/dashboard/charges/{cid}/refund", headers=H, json={"reason": "x"})

    logs = client.get("/dashboard/audit-logs", headers=H).json()
    actions = {log["action"] for log in logs}
    assert {"auth.register", "api_key.create", "charge.create", "charge.refund"} <= actions
    # actor + ip are captured
    assert all(log["actor"] for log in logs)
    assert any(log["ip"] for log in logs)


def test_audit_requires_auth(client):
    assert client.get("/dashboard/audit-logs").status_code == 401


def test_audit_scoped_to_merchant(client, merchant):
    import secrets

    # register + act as another merchant; their actions must not leak into this merchant's log
    other_tok = client.post("/auth/register", json={
        "email": f"o_{secrets.token_hex(4)}@panpay.io", "password": "secret123",
        "business_name": "Other", "promptpay_id": "0899999999",
    }).json()["access_token"]
    create_charge(client, {"Authorization": f"Bearer {other_tok}"}, 10.0)

    logs = client.get("/dashboard/audit-logs", headers=merchant["headers"]).json()
    assert all(log["actor"] == merchant["email"] for log in logs)
