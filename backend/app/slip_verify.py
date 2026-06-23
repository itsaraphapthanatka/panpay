"""Pluggable slip-verification providers.

A verifier takes whatever the customer submitted on the checkout page (an
uploaded slip image and/or a QR payload string) plus the expected charge, and
returns a normalized VerifyResult. Swap providers via SLIP_PROVIDER in .env:

    dev      -> local testing, no bank (accepts the auto-read QR as the reference)
    slipok   -> https://slipok.com
    easyslip -> https://easyslip.com
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from .banks import bank_name
from .config import settings
from .models import utcnow
from .slip_qr import parse_slip_qr


@dataclass
class VerifyResult:
    success: bool
    trans_ref: str | None = None
    amount: float | None = None
    sender_name: str | None = None
    sender_bank: str | None = None
    receiver_name: str | None = None
    receiver_bank: str | None = None
    transferred_at: datetime | None = None
    provider: str = "dev"
    raw: dict = field(default_factory=dict)
    error: str | None = None


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _amount_value(amount) -> float | None:
    """Providers report amount as a number or as {"amount": <number>, ...}."""
    if amount is None:
        return None
    if isinstance(amount, dict):
        amount = amount.get("amount")
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


class SlipVerifier:
    name = "base"

    def verify(
        self,
        *,
        expected_amount: float,
        file_bytes: bytes | None,
        qr_payload: str | None,
        trans_ref: str | None,
    ) -> VerifyResult:
        raise NotImplementedError


class DevVerifier(SlipVerifier):
    """Local provider for end-to-end testing without a real bank.

    With DEV_AUTO_VERIFY=true it accepts the payment as long as the customer
    submitted *something* (a file or a trans_ref) and reports the expected
    amount. A unique trans_ref is generated when the client did not provide one
    so the unique-slip constraint still holds.
    """

    name = "dev"

    def verify(self, *, expected_amount, file_bytes, qr_payload, trans_ref):
        submitted_something = bool(file_bytes or qr_payload or trans_ref)
        if not submitted_something:
            return VerifyResult(success=False, provider=self.name, error="no_slip_submitted")
        # A real reference (an explicit trans_ref or a QR auto-read from the slip)
        # is enough on its own; otherwise we only proceed when auto-verify is on.
        real_ref = trans_ref or qr_payload
        if not settings.dev_auto_verify and not real_ref:
            return VerifyResult(success=False, provider=self.name, error="trans_ref_required")
        ref = real_ref or ("DEV" + secrets.token_hex(10).upper())
        qr_fields = parse_slip_qr(qr_payload) if qr_payload else {}
        return VerifyResult(
            success=True,
            trans_ref=ref,
            amount=expected_amount,
            sender_name="ลูกค้าทดสอบ (DEV)",
            sender_bank="ทดสอบ (DEV)",
            transferred_at=utcnow(),
            provider=self.name,
            raw={
                "mode": "dev",
                "auto_verify": settings.dev_auto_verify,
                "qr_decoded": bool(qr_payload),
                "qr_fields": qr_fields,
            },
        )


class SlipOKVerifier(SlipVerifier):
    """Real verification via SlipOK (https://slipok.com)."""

    name = "slipok"
    BASE = "https://api.slipok.com/api/line/apikey"

    def verify(self, *, expected_amount, file_bytes, qr_payload, trans_ref):
        if not settings.slipok_api_key or not settings.slipok_branch_id:
            return VerifyResult(success=False, provider=self.name, error="slipok_not_configured")

        url = f"{self.BASE}/{settings.slipok_branch_id}"
        headers = {"x-authorization": settings.slipok_api_key}
        try:
            if file_bytes:
                resp = httpx.post(
                    url,
                    headers=headers,
                    files={"files": ("slip.png", file_bytes, "image/png")},
                    data={"amount": str(expected_amount)},
                    timeout=20,
                )
            elif qr_payload:
                resp = httpx.post(
                    url,
                    headers=headers,
                    json={"data": qr_payload, "amount": expected_amount},
                    timeout=20,
                )
            else:
                return VerifyResult(success=False, provider=self.name, error="no_slip_submitted")
        except httpx.HTTPError as exc:
            return VerifyResult(success=False, provider=self.name, error=f"http_error: {exc}")

        body = resp.json() if resp.content else {}
        if resp.status_code != 200 or not body.get("success"):
            return VerifyResult(
                success=False,
                provider=self.name,
                raw=body,
                error=str(body.get("message") or f"status_{resp.status_code}"),
            )

        data = body.get("data", {})
        return VerifyResult(
            success=True,
            trans_ref=data.get("transRef"),
            amount=_amount_value(data.get("amount")),
            sender_name=(data.get("sender") or {}).get("displayName"),
            sender_bank=data.get("sendingBank"),
            receiver_name=(data.get("receiver") or {}).get("displayName"),
            receiver_bank=data.get("receivingBank"),
            transferred_at=_parse_dt(data.get("transTimestamp") or data.get("transDate")),
            provider=self.name,
            raw=body,
        )


class EasySlipVerifier(SlipVerifier):
    """Real verification via EasySlip (https://easyslip.com).

    Accepts either the slip image or the decoded QR payload string.
    """

    name = "easyslip"
    URL = "https://developer.easyslip.com/api/v1/verify"

    def verify(self, *, expected_amount, file_bytes, qr_payload, trans_ref):
        if not settings.easyslip_api_key:
            return VerifyResult(success=False, provider=self.name, error="easyslip_not_configured")

        headers = {"Authorization": f"Bearer {settings.easyslip_api_key}"}
        try:
            if file_bytes:
                resp = httpx.post(
                    self.URL,
                    headers=headers,
                    files={"file": ("slip.png", file_bytes, "image/png")},
                    timeout=20,
                )
            elif qr_payload:
                resp = httpx.post(
                    self.URL, headers=headers, json={"payload": qr_payload}, timeout=20
                )
            else:
                return VerifyResult(success=False, provider=self.name, error="no_slip_submitted")
        except httpx.HTTPError as exc:
            return VerifyResult(success=False, provider=self.name, error=f"http_error: {exc}")

        body = resp.json() if resp.content else {}
        data = body.get("data")
        if resp.status_code != 200 or not data:
            return VerifyResult(
                success=False,
                provider=self.name,
                raw=body,
                error=str(body.get("message") or body.get("status") or f"status_{resp.status_code}"),
            )

        sender = data.get("sender") or {}
        receiver = data.get("receiver") or {}

        def _acct_name(node):
            acct = (node.get("account") or {}).get("name") or {}
            return acct.get("th") or acct.get("en")

        def _bank(node):
            bank = node.get("bank") or {}
            return bank.get("name") or bank_name(bank.get("id"))

        return VerifyResult(
            success=True,
            trans_ref=data.get("transRef"),
            amount=_amount_value(data.get("amount")),
            sender_name=_acct_name(sender),
            sender_bank=_bank(sender),
            receiver_name=_acct_name(receiver),
            receiver_bank=_bank(receiver),
            transferred_at=_parse_dt(data.get("date")),
            provider=self.name,
            raw=body,
        )


_PROVIDERS = {
    "dev": DevVerifier,
    "slipok": SlipOKVerifier,
    "easyslip": EasySlipVerifier,
}


def get_verifier() -> SlipVerifier:
    return _PROVIDERS.get(settings.slip_provider, DevVerifier)()
