import io

from PIL import Image

from .helpers import create_charge, make_qr_png, pay_charge


def _blank_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_checkout_view_renders_qr(client, merchant):
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    r = client.get(f"/checkout/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["qr_image"].startswith("data:image/png;base64,")
    assert body["business_name"] == "Test Shop"


def test_slip_qr_autodecoded_becomes_trans_ref(client, merchant):
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    qr = "0046SLIPREF000ABC"
    r = client.post(f"/checkout/{cid}/slip", files={"file": ("s.png", make_qr_png(qr), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "paid"
    assert body["payment"]["trans_ref"] == qr
    assert body["payment"]["transferred_at"]


def test_duplicate_slip_rejected(client, merchant):
    qr = "0046DUP123"
    c1 = create_charge(client, merchant["headers"], 100.0)["id"]
    c2 = create_charge(client, merchant["headers"], 100.0)["id"]
    assert client.post(f"/checkout/{c1}/slip", files={"file": ("s.png", make_qr_png(qr), "image/png")}).status_code == 200
    r = client.post(f"/checkout/{c2}/slip", files={"file": ("s.png", make_qr_png(qr), "image/png")})
    assert r.status_code == 409


def test_image_without_qr_rejected_when_no_autoverify(client, merchant, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "dev_auto_verify", False)
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    r = client.post(f"/checkout/{cid}/slip", files={"file": ("blank.png", _blank_png(), "image/png")})
    assert r.status_code == 422


def test_pay_already_paid_is_idempotent(client, merchant):
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    assert pay_charge(client, cid).status_code == 200
    # paying again returns current paid state, not an error
    r = client.post(f"/checkout/{cid}/slip", data={"trans_ref": "whatever"})
    assert r.status_code == 200
    assert r.json()["status"] == "paid"


def test_receipt_requires_payment(client, merchant):
    cid = create_charge(client, merchant["headers"], 100.0)["id"]
    assert client.get(f"/checkout/{cid}/receipt.pdf").status_code == 409
    pay_charge(client, cid)
    r = client.get(f"/checkout/{cid}/receipt.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
