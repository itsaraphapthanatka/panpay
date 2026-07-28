"""Bank-notification ingest — settle charges without a customer slip.

A small forwarder app on the merchant's phone (e.g. MacroDroid/Tasker reading the
bank app's incoming-transfer notification) POSTs the credited amount here. We
match it to a pending charge of the same amount and mark it paid automatically.

Auth: the merchant's API secret key (X-API-Key or Authorization: Bearer sk_...),
so each forwarder is bound to exactly one merchant / bank account.

Matching is by amount within a time window. If two pending charges share the same
amount we settle the oldest and report how many candidates there were, so the
merchant can spot ambiguity. Use unique amounts (satang) to avoid collisions.
"""

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import audit
from ..charge_ops import settle_charge_paid
from ..database import get_db
from ..deps import get_api_merchant
from ..models import Charge, Merchant, ReceivingAccount, utcnow
from ..ratelimit import limit_api
from ..schemas import BankIncomingRequest, BankIncomingResult
from ..settings_store import AUTO_BANK_CHECK, ensure_ingest_key, get_bool
from ..topup_ops import account_matches

router = APIRouter(prefix="/bank", tags=["bank ingest"], dependencies=[Depends(limit_api)])

AMOUNT_TOLERANCE = 0.001


def _charge_promptpay(db: Session, charge: Charge) -> str | None:
    """The PromptPay id an incoming transfer for this charge would land in."""
    if charge.receiving_account_id:
        acct = db.get(ReceivingAccount, charge.receiving_account_id)
        if acct:
            return acct.promptpay_id
    merchant = db.get(Merchant, charge.merchant_id)
    return merchant.promptpay_id if merchant else None


@router.post("/incoming", response_model=BankIncomingResult)
def incoming(
    body: BankIncomingRequest,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    if not get_bool(db, AUTO_BANK_CHECK, default=True):
        return BankIncomingResult(matched=False, reason="auto_check_disabled",
                                  amount=body.amount, candidates=0)

    now = utcnow()
    candidates = (
        db.query(Charge)
        .filter(
            Charge.merchant_id == merchant.id,
            Charge.status == "pending",
            func.abs(Charge.amount - body.amount) <= AMOUNT_TOLERANCE,
            (Charge.expires_at.is_(None)) | (Charge.expires_at >= now),
        )
        .order_by(Charge.created_at.asc())
        .all()
    )

    if not candidates:
        audit.record(db, action="bank.incoming.unmatched", actor="bank", merchant_id=merchant.id,
                     request=request, extra={"amount": body.amount, "ref": body.ref})
        return BankIncomingResult(matched=False, reason="no_pending_charge_for_amount",
                                  amount=body.amount, candidates=0)
    if len(candidates) > 1:
        # Ambiguous: multiple pending charges share this amount. Don't auto-settle
        # (could credit the wrong one) — fall back to slip/manual confirmation.
        audit.record(db, action="bank.incoming.ambiguous", actor="bank", merchant_id=merchant.id,
                     request=request, extra={"amount": body.amount, "candidates": len(candidates)})
        return BankIncomingResult(matched=False, reason="ambiguous_amount",
                                  amount=body.amount, candidates=len(candidates))

    charge = candidates[0]
    trans_ref = body.ref or ("BANK" + secrets.token_hex(10).upper())
    raw = {"source": "bank_notify", "ref": body.ref, "sender_name": body.sender_name, **body.raw}

    settle_charge_paid(
        db, background, charge,
        trans_ref=trans_ref,
        amount=float(charge.amount),
        sender_name=body.sender_name,
        transferred_at=body.transferred_at or now,
        provider="bank_notify",
        raw=raw,
    )
    audit.record(db, action="charge.bank_paid", actor="bank", merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request,
                 extra={"amount": body.amount, "candidates": len(candidates)})

    return BankIncomingResult(matched=True, charge_id=charge.id, amount=float(charge.amount),
                              candidates=len(candidates))


@router.post("/incoming/platform", response_model=BankIncomingResult)
def incoming_platform(
    body: BankIncomingRequest,
    request: Request,
    background: BackgroundTasks,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Platform-wide charge match for a shared collection account.

    Unlike /bank/incoming (bound to one merchant via its API key), this settles a
    pending charge for ANY merchant, so a single forwarder/LINE bridge watching one
    shared bank account can confirm every merchant that collects into it. Auth is
    the platform top-up ingest key. When `account` is given, only charges billed to
    that PromptPay account are considered (so other accounts are never matched).
    Global unique-satang amounts keep the amount->charge mapping unambiguous.
    """
    expected = ensure_ingest_key(db)
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingest key")
    if not get_bool(db, AUTO_BANK_CHECK, default=True):
        return BankIncomingResult(matched=False, reason="auto_check_disabled",
                                  amount=body.amount, candidates=0)

    now = utcnow()
    candidates = (
        db.query(Charge)
        .filter(
            Charge.status == "pending",
            func.abs(Charge.amount - body.amount) <= AMOUNT_TOLERANCE,
            (Charge.expires_at.is_(None)) | (Charge.expires_at >= now),
        )
        .order_by(Charge.created_at.asc())
        .all()
    )
    if body.account:
        candidates = [c for c in candidates if account_matches(_charge_promptpay(db, c), body.account)]

    if not candidates:
        audit.record(db, action="bank.incoming.unmatched", actor="bank_platform", request=request,
                     extra={"amount": body.amount, "ref": body.ref, "account": body.account})
        return BankIncomingResult(matched=False, reason="no_pending_charge_for_amount",
                                  amount=body.amount, candidates=0)
    if len(candidates) > 1:
        audit.record(db, action="bank.incoming.ambiguous", actor="bank_platform", request=request,
                     extra={"amount": body.amount, "candidates": len(candidates)})
        return BankIncomingResult(matched=False, reason="ambiguous_amount",
                                  amount=body.amount, candidates=len(candidates))

    charge = candidates[0]
    trans_ref = body.ref or ("BANK" + secrets.token_hex(10).upper())
    raw = {"source": "bank_notify_platform", "ref": body.ref, "sender_name": body.sender_name, **body.raw}
    settle_charge_paid(
        db, background, charge,
        trans_ref=trans_ref, amount=float(charge.amount),
        sender_name=body.sender_name, transferred_at=body.transferred_at or now,
        provider="bank_notify", raw=raw,
    )
    audit.record(db, action="charge.bank_paid", actor="bank_platform", merchant_id=charge.merchant_id,
                 target_type="charge", target_id=charge.id, request=request, extra={"amount": body.amount})
    return BankIncomingResult(matched=True, charge_id=charge.id, amount=float(charge.amount),
                              candidates=len(candidates))


@router.post("/incoming/for-merchant", response_model=BankIncomingResult)
def incoming_for_merchant(
    body: BankIncomingRequest,
    request: Request,
    background: BackgroundTasks,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Settle a pending charge for ONE specific merchant (their per-merchant LINE
    bot watches their own bank account). Auth: platform ingest key; the merchant
    is identified by body.merchant_id, so the manager needs no merchant API keys."""
    expected = ensure_ingest_key(db)
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingest key")
    if not body.merchant_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "merchant_id is required")
    if not get_bool(db, AUTO_BANK_CHECK, default=True):
        return BankIncomingResult(matched=False, reason="auto_check_disabled",
                                  amount=body.amount, candidates=0)

    now = utcnow()
    candidates = (
        db.query(Charge)
        .filter(
            Charge.merchant_id == body.merchant_id,
            Charge.status == "pending",
            func.abs(Charge.amount - body.amount) <= AMOUNT_TOLERANCE,
            (Charge.expires_at.is_(None)) | (Charge.expires_at >= now),
        )
        .order_by(Charge.created_at.asc())
        .all()
    )
    if not candidates:
        return BankIncomingResult(matched=False, reason="no_pending_charge_for_amount",
                                  amount=body.amount, candidates=0)
    if len(candidates) > 1:
        return BankIncomingResult(matched=False, reason="ambiguous_amount",
                                  amount=body.amount, candidates=len(candidates))

    charge = candidates[0]
    trans_ref = body.ref or ("BANK" + secrets.token_hex(10).upper())
    raw = {"source": "bank_notify_merchant", "ref": body.ref, "sender_name": body.sender_name, **body.raw}
    settle_charge_paid(
        db, background, charge,
        trans_ref=trans_ref, amount=float(charge.amount),
        sender_name=body.sender_name, transferred_at=body.transferred_at or now,
        provider="bank_notify", raw=raw,
    )
    audit.record(db, action="charge.bank_paid", actor="bank_merchant", merchant_id=charge.merchant_id,
                 target_type="charge", target_id=charge.id, request=request, extra={"amount": body.amount})
    return BankIncomingResult(matched=True, charge_id=charge.id, amount=float(charge.amount),
                              candidates=len(candidates))
