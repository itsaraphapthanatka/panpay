"""Pluggable slip-verification providers.

A verifier takes whatever the customer submitted on the checkout page (an
uploaded slip image and/or a QR payload string) plus the expected charge, and
returns a normalized VerifyResult. Swap providers via SLIP_PROVIDER in .env:

    dev      -> local testing, no bank (accepts the auto-read QR as the reference)
    slipok   -> https://slipok.com
    easyslip -> https://easyslip.com
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger("uvicorn.error")

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


class Slip2GoVerifier(SlipVerifier):
    """Real verification via Slip2Go (https://slip2go.com).

    Two endpoints (base URL + Bearer secret come from the account):
      - image: POST {base}/api/verify-slip/qr-image/info  (multipart: file [+ payload])
      - qr   : POST {base}/api/verify-slip/qr-code/info    (json: {"payload": {"qrCode": ...}})

    NOTE: the response field mapping below follows the common Thai slip-verify
    shape ({"data": {...}}). Adjust _map() once the exact Response is confirmed —
    the full body is always stored in `raw`.
    """

    name = "slip2go"

    # Codes that mean "genuine slip we may accept". 200000 = slip found in the
    # bank; 200200 = slip valid and matched the conditions we sent. All other
    # 2004xx/2005xx codes are rejections even though HTTP is 200.
    SUCCESS_CODES = {"200000", "200200"}

    def _url(self, path: str) -> str:
        return f"{settings.slip2go_base_url.rstrip('/')}{path}"

    def verify(self, *, expected_amount, file_bytes, qr_payload, trans_ref):
        if not settings.slip2go_secret_key:
            return VerifyResult(success=False, provider=self.name, error="slip2go_not_configured")

        headers = {"Authorization": f"Bearer {settings.slip2go_secret_key}"}
        check = {"checkDuplicate": settings.slip2go_check_duplicate}
        try:
            if file_bytes:
                resp = httpx.post(
                    self._url("/api/verify-slip/qr-image/info"),
                    headers=headers,
                    files={"file": ("slip.png", file_bytes, "image/png")},
                    data={"payload": json.dumps(check)},
                    timeout=20,
                )
            elif qr_payload:
                resp = httpx.post(
                    self._url("/api/verify-slip/qr-code/info"),
                    headers={**headers, "Content-Type": "application/json"},
                    json={"payload": {"qrCode": qr_payload, **check}},
                    timeout=20,
                )
            else:
                return VerifyResult(success=False, provider=self.name, error="no_slip_submitted")
        except httpx.HTTPError as exc:
            return VerifyResult(success=False, provider=self.name, error=f"http_error: {exc}")

        body = resp.json() if resp.content else {}
        # Log the raw response so field mapping can be confirmed against real slips.
        logger.info("slip2go response (http %s): %s", resp.status_code, json.dumps(body, ensure_ascii=False)[:1500])

        # Slip2Go returns HTTP 200 for EVERY case; the real status is in `code`.
        # Only a genuine, condition-matching slip may be accepted. Everything else
        # (fraud 200500, duplicate 200501, not-found 200404, mismatch 200401/2/3,
        # bank error 200502) must be rejected.
        code = str((body or {}).get("code") or "")
        data = body.get("data") if isinstance(body, dict) else None
        if code not in self.SUCCESS_CODES or not data:
            msg = (body or {}).get("message") or code or f"status_{resp.status_code}"
            return VerifyResult(success=False, provider=self.name, raw=body,
                                error=f"{code} {msg}".strip())
        return self._map(data, body)

    @staticmethod
    def _map(data: dict, body: dict) -> VerifyResult:
        # Field names confirmed against Slip2Go's documented response:
        #   data.transRef, data.amount, data.dateTime,
        #   data.{sender,receiver}.account.name, data.{sender,receiver}.bank.{id,name}
        sender = data.get("sender") or {}
        receiver = data.get("receiver") or {}

        def acct_name(node):
            return (node.get("account") or {}).get("name")

        def bank_label(node):
            bank = node.get("bank") or {}
            return bank.get("name") or bank_name(bank.get("id"))

        return VerifyResult(
            success=True,
            # transRef is the bank's transaction reference — unique, used to block re-used slips.
            trans_ref=data.get("transRef") or data.get("referenceId"),
            amount=_amount_value(data.get("amount")),
            sender_name=acct_name(sender),
            sender_bank=bank_label(sender),
            receiver_name=acct_name(receiver),
            receiver_bank=bank_label(receiver),
            transferred_at=_parse_dt(data.get("dateTime")),
            provider="slip2go",
            raw=body,
        )


_PROVIDERS = {
    "dev": DevVerifier,
    "slipok": SlipOKVerifier,
    "easyslip": EasySlipVerifier,
    "slip2go": Slip2GoVerifier,
}


def get_verifier() -> SlipVerifier:
    return _PROVIDERS.get(settings.slip_provider, DevVerifier)()
