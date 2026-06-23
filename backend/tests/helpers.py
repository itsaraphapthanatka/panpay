"""Shared helpers for tests."""

import io
import secrets

import qrcode


def make_qr_png(data: str | None = None) -> bytes:
    """Render a QR image (defaults to a unique slip-like payload)."""
    data = data or ("0046" + secrets.token_hex(8).upper())
    buf = io.BytesIO()
    qrcode.make(data).save(buf, format="PNG")
    return buf.getvalue()


def create_charge(client, headers, amount=100.0, **extra):
    body = {"amount": amount, **extra}
    r = client.post("/dashboard/charges", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def pay_charge(client, charge_id, qr_data: str | None = None):
    """Submit a slip image to mark a charge paid (dev verifier auto-verifies)."""
    return client.post(
        f"/checkout/{charge_id}/slip",
        files={"file": ("slip.png", make_qr_png(qr_data), "image/png")},
    )
