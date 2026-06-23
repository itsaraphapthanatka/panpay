from .helpers import pay_charge


def _plan(client, H):
    return client.post("/dashboard/plans", headers=H, json={"name": "P", "amount": 100}).json()


def test_invoice_and_payment_notifications_recorded(client, merchant):
    H = merchant["headers"]
    plan = _plan(client, H)
    created = client.post("/dashboard/subscriptions", headers=H, json={
        "plan_id": plan["id"], "customer_name": "A",
        "customer_email": "a@example.com", "customer_phone": "0812345678",
    }).json()

    notifs = client.get("/dashboard/notifications", headers=H).json()
    issued = [n for n in notifs if n["event"] == "invoice.issued"]
    # email + sms for the first invoice
    assert {n["channel"] for n in issued} == {"email", "sms"}
    # no SMTP/SMS configured in tests -> recorded as skipped via console provider
    assert all(n["status"] == "skipped" and n["provider"] == "console" for n in issued)

    pay_charge(client, created["invoice"]["id"])
    notifs = client.get("/dashboard/notifications", headers=H).json()
    paid = [n for n in notifs if n["event"] == "payment.received"]
    assert {n["channel"] for n in paid} == {"email", "sms"}


def test_no_contact_no_notifications(client, merchant):
    H = merchant["headers"]
    plan = _plan(client, H)
    client.post("/dashboard/subscriptions", headers=H,
                json={"plan_id": plan["id"], "customer_name": "NoContact"})
    notifs = client.get("/dashboard/notifications", headers=H).json()
    assert notifs == []  # no email/phone -> nothing sent or recorded


def test_line_channel_sent_when_configured(client, merchant, monkeypatch):
    import app.notifications as nt

    monkeypatch.setattr(nt.settings, "line_channel_access_token", "test-token")
    calls = []

    class _Resp:
        status_code = 200
        content = b"{}"

        @staticmethod
        def json():
            return {}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})
        return _Resp()

    monkeypatch.setattr(nt.httpx, "post", fake_post)

    H = merchant["headers"]
    plan = _plan(client, H)
    client.post("/dashboard/subscriptions", headers=H, json={
        "plan_id": plan["id"], "customer_name": "A", "customer_line_id": "U1234567890",
    })

    line = [n for n in client.get("/dashboard/notifications", headers=H).json() if n["channel"] == "line"]
    assert line and line[0]["status"] == "sent" and line[0]["recipient"] == "U1234567890"
    # called the LINE push endpoint with the right shape
    assert calls and calls[-1]["url"].endswith("/v2/bot/message/push")
    assert calls[-1]["json"]["to"] == "U1234567890"
    assert calls[-1]["json"]["messages"][0]["type"] == "text"


def test_line_skipped_without_token(client, merchant):
    H = merchant["headers"]
    plan = _plan(client, H)
    client.post("/dashboard/subscriptions", headers=H, json={
        "plan_id": plan["id"], "customer_name": "A", "customer_line_id": "U999",
    })
    line = [n for n in client.get("/dashboard/notifications", headers=H).json() if n["channel"] == "line"]
    assert line and line[0]["status"] == "skipped"


def test_email_only_records_single_channel(client, merchant):
    H = merchant["headers"]
    plan = _plan(client, H)
    client.post("/dashboard/subscriptions", headers=H, json={
        "plan_id": plan["id"], "customer_name": "A", "customer_email": "only@example.com",
    })
    issued = [n for n in client.get("/dashboard/notifications", headers=H).json() if n["event"] == "invoice.issued"]
    assert [n["channel"] for n in issued] == ["email"]
