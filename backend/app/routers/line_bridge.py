"""Inbound endpoint for the experimental LINE bridge (line-bridge/ Node service).

The bridge logs into a LINE account (via @evex/linejs), reads bank transfer
notification messages, parses the amount, and POSTs it here authenticated with
the merchant's API key. We match it to a single pending charge of that exact
amount and mark it paid.

⚠️ This is a best-effort convenience channel, NOT authoritative verification:
amount-only matching is ambiguous and notification text can be spoofed. Use the
slip-verification API as the real source of truth.
"""

import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_api_merchant
from ..models import Charge, Merchant, Payment, Subscription, utcnow
from ..ratelimit import limit_api
from ..settings_store import (
    LINE_BOT_RECONNECT,
    LINE_BOT_STATE,
    ensure_ingest_key,
    get_str,
    line_bot_action_key,
    line_bot_enabled_key,
    line_bot_enabled_merchant_ids,
    line_bot_state_key,
    set_str,
)
from ..subscription_ops import advance_on_payment
from ..webhooks import deliver_webhook, enqueue_charge_event, enqueue_subscription_event

router = APIRouter(prefix="/v1/line", tags=["line bridge"], dependencies=[Depends(limit_api)])

AMOUNT_TOLERANCE = 0.005
MATCH_WINDOW_HOURS = 24


class BotState(BaseModel):
    # starting | awaiting_qr | connected | logged_out
    status: str
    qr_url: str | None = None
    display_name: str | None = None


@router.post("/bot-state")
def bot_state(
    body: BotState,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """The LINE bridge publishes its connection state here (auth: platform ingest
    key) so the admin console can show the login QR / status. Returns whether a
    reconnect was requested; the flag is one-shot (cleared as it's handed out)."""
    expected = ensure_ingest_key(db)
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingest key")

    set_str(db, LINE_BOT_STATE, json.dumps({
        "status": body.status,
        "qr_url": body.qr_url,
        "display_name": body.display_name,
        "updated_at": utcnow().isoformat(),
    }))

    reconnect = get_str(db, LINE_BOT_RECONNECT, "") == "1"
    if reconnect:
        set_str(db, LINE_BOT_RECONNECT, "")  # consume: act on it once
    return {"reconnect": reconnect}


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


# ---- Multi-tenant manager (per-merchant bots) ----
class ManagerState(BaseModel):
    merchant_id: str
    status: str                       # starting | awaiting_qr | connected
    qr_url: str | None = None
    display_name: str | None = None


def _require_ingest(x_ingest_key: str | None, db: Session) -> None:
    expected = ensure_ingest_key(db)
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingest key")


@router.get("/manager/merchants")
def manager_merchants(x_ingest_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Merchant ids that want a LINE bot running (the manager reconciles to this)."""
    _require_ingest(x_ingest_key, db)
    return {"merchant_ids": line_bot_enabled_merchant_ids(db)}


@router.post("/manager/state")
def manager_state(
    body: ManagerState,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """The manager publishes one merchant's bot state and learns the desired
    action (enabled? one-shot reconnect?) to reconcile against."""
    _require_ingest(x_ingest_key, db)
    set_str(db, line_bot_state_key(body.merchant_id), json.dumps({
        "status": body.status,
        "qr_url": body.qr_url,
        "display_name": body.display_name,
        "updated_at": utcnow().isoformat(),
    }))
    enabled = get_str(db, line_bot_enabled_key(body.merchant_id), "") == "1"
    action = get_str(db, line_bot_action_key(body.merchant_id), "")
    if action:
        set_str(db, line_bot_action_key(body.merchant_id), "")  # one-shot
    return {"enabled": enabled, "action": action}


@router.get("/manager/balance/{merchant_id}")
def manager_balance(
    merchant_id: str,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Wallet balance for a merchant, so the manager can answer "ยอดเงิน"."""
    _require_ingest(x_ingest_key, db)
    from ..billing import credit_rate

    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return {
        "balance": float(merchant.balance or 0),
        "credit_per_transaction": credit_rate(db, merchant),
        "business_name": merchant.business_name,
    }
