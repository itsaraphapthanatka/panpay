from app.security import sign_webhook

from .helpers import create_charge, pay_charge


class _FakeResp:
    status_code = 200
    content = b""


def test_webhook_delivered_with_valid_signature(client, merchant, monkeypatch):
    import app.webhooks as wh

    calls = []

    def fake_post(url, content=None, headers=None, timeout=None):
        calls.append({"url": url, "content": content, "headers": headers})
        return _FakeResp()

    monkeypatch.setattr(wh.httpx, "post", fake_post)

    H = merchant["headers"]
    client.patch("/dashboard/settings", headers=H, json={"webhook_url": "https://shop.example/wh"})
    secret = client.get("/auth/me", headers=H).json()["webhook_secret"]

    cid = create_charge(client, H, 77.0)["id"]
    pay_charge(client, cid)  # fires the webhook as a background task

    assert calls, "webhook was not delivered"
    call = calls[-1]
    assert call["url"] == "https://shop.example/wh"
    assert call["headers"]["X-Panpay-Event"] == "charge.paid"
    assert call["headers"]["X-Panpay-Signature"] == sign_webhook(secret, call["content"])


def test_no_webhook_when_url_unset(client, merchant, monkeypatch):
    import app.webhooks as wh

    calls = []
    monkeypatch.setattr(wh.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResp())

    cid = create_charge(client, merchant["headers"], 10.0)["id"]
    pay_charge(client, cid)
    assert calls == []  # merchant has no webhook_url


def test_refund_fires_refunded_event(client, merchant, monkeypatch):
    import app.webhooks as wh

    events = []

    def fake_post(url, content=None, headers=None, timeout=None):
        events.append(headers["X-Panpay-Event"])
        return _FakeResp()

    monkeypatch.setattr(wh.httpx, "post", fake_post)
    H = merchant["headers"]
    client.patch("/dashboard/settings", headers=H, json={"webhook_url": "https://shop.example/wh"})
    cid = create_charge(client, H, 50.0)["id"]
    pay_charge(client, cid)
    client.post(f"/dashboard/charges/{cid}/refund", headers=H, json={"reason": "x"})
    assert "charge.paid" in events and "charge.refunded" in events
