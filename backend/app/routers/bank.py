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

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import audit
from ..charge_ops import settle_charge_paid
from ..database import get_db
from ..deps import get_api_merchant
from ..models import Charge, Merchant, utcnow
from ..ratelimit import limit_api
from ..schemas import BankIncomingRequest, BankIncomingResult

router = APIRouter(prefix="/bank", tags=["bank ingest"], dependencies=[Depends(limit_api)])

AMOUNT_TOLERANCE = 0.001


@router.post("/incoming", response_model=BankIncomingResult)
def incoming(
    body: BankIncomingRequest,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
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
