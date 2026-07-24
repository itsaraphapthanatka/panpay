"""Inbound endpoint for the experimental LINE bridge (line-bridge/ Node service).

The bridge logs into a LINE account (via @evex/linejs), reads bank transfer
notification messages, parses the amount, and POSTs it here authenticated with
the merchant's API key. We match it to a single pending charge of that exact
amount and mark it paid.

⚠️ This is a best-effort convenience channel, NOT authoritative verification:
amount-only matching is ambiguous and notification text can be spoofed. Use the
slip-verification API as the real source of truth.
"""

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_api_merchant
from ..models import Charge, Merchant, Payment, Subscription, utcnow
from ..ratelimit import limit_api
from ..subscription_ops import advance_on_payment
from ..webhooks import deliver_webhook, enqueue_charge_event, enqueue_subscription_event

router = APIRouter(prefix="/v1/line", tags=["line bridge"], dependencies=[Depends(limit_api)])

AMOUNT_TOLERANCE = 0.005
MATCH_WINDOW_HOURS = 24


class LineTransfer(BaseModel):
    amount: float = Field(gt=0)
    message_id: str
    text: str | None = None
    sender: str | None = None


@router.post("/transfer")
def line_transfer(
    body: LineTransfer,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    trans_ref = f"LINE:{body.message_id}"
    if db.query(Payment).filter(Payment.trans_ref == trans_ref).first():
        return {"matched": False, "reason": "already_processed"}

    since = utcnow() - timedelta(hours=MATCH_WINDOW_HOURS)
    candidates = [
        c
        for c in db.query(Charge)
        .filter(Charge.merchant_id == merchant.id, Charge.status == "pending", Charge.created_at >= since)
        .order_by(Charge.created_at.desc())
        .all()
        if abs(float(c.amount) - body.amount) <= AMOUNT_TOLERANCE
    ]
    if not candidates:
        return {"matched": False, "reason": "no_pending_charge"}
    if len(candidates) > 1:
        return {"matched": False, "reason": "ambiguous", "count": len(candidates)}

    charge = candidates[0]
    db.add(Payment(
        charge_id=charge.id, trans_ref=trans_ref, amount=body.amount,
        sender_name=body.sender, provider="line_notify", transferred_at=utcnow(),
        raw={"text": body.text, "message_id": body.message_id},
    ))
    charge.status = "paid"
    charge.paid_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"matched": False, "reason": "already_processed"}
    db.refresh(charge)

    if charge.subscription_id:
        event = advance_on_payment(db, charge)
        if event:
            sub = db.get(Subscription, charge.subscription_id)
            d = enqueue_subscription_event(db, sub, charge.merchant, event)
            if d:
                background.add_task(deliver_webhook, d.id, charge.merchant.webhook_secret)

    delivery = enqueue_charge_event(db, charge, charge.merchant, "charge.paid")
    if delivery:
        background.add_task(deliver_webhook, delivery.id, charge.merchant.webhook_secret)

    return {"matched": True, "charge_id": charge.id, "amount": float(charge.amount)}
