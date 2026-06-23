"""Outbound webhook delivery with HMAC signing and a few retries."""

import json
import time

import httpx
from sqlalchemy.orm import Session

from .models import Charge, Merchant, WebhookDelivery, utcnow
from .security import sign_webhook

MAX_ATTEMPTS = 4
BACKOFF_SECONDS = [0, 2, 5, 15]


def build_charge_payload(charge: Charge, event: str) -> dict:
    p = charge.payment
    payment = None
    if p:
        payment = {
            "trans_ref": p.trans_ref,
            "amount": float(p.amount),
            "sender_name": p.sender_name,
            "sender_bank": p.sender_bank,
            "receiver_name": p.receiver_name,
            "receiver_bank": p.receiver_bank,
            "transferred_at": p.transferred_at.isoformat() if p.transferred_at else None,
            "provider": p.provider,
        }
    return {
        "event": event,
        "created": utcnow().isoformat(),
        "data": {
            "id": charge.id,
            "amount": float(charge.amount),
            "currency": charge.currency,
            "status": charge.status,
            "reference": charge.reference,
            "description": charge.description,
            "paid_at": charge.paid_at.isoformat() if charge.paid_at else None,
            "metadata": charge.extra or {},
            "subscription_id": charge.subscription_id,
            "payment": payment,
        },
    }


def deliver_webhook(delivery_id: str, secret: str) -> None:
    """Run as a background task. Opens its own DB session."""
    from .database import SessionLocal

    db: Session = SessionLocal()
    try:
        delivery = db.get(WebhookDelivery, delivery_id)
        if not delivery:
            return
        body = json.dumps(delivery.payload, separators=(",", ":")).encode("utf-8")
        signature = sign_webhook(secret, body)
        headers = {
            "Content-Type": "application/json",
            "X-Panpay-Event": delivery.event,
            "X-Panpay-Signature": signature,
        }

        for attempt in range(MAX_ATTEMPTS):
            if BACKOFF_SECONDS[attempt]:
                time.sleep(BACKOFF_SECONDS[attempt])
            delivery.attempts = attempt + 1
            try:
                resp = httpx.post(delivery.url, content=body, headers=headers, timeout=15)
                delivery.last_status_code = resp.status_code
                if 200 <= resp.status_code < 300:
                    delivery.status = "success"
                    delivery.delivered_at = utcnow()
                    delivery.last_error = None
                    db.commit()
                    return
                delivery.last_error = f"status_{resp.status_code}"
            except httpx.HTTPError as exc:
                delivery.last_status_code = None
                delivery.last_error = str(exc)
            db.commit()

        delivery.status = "failed"
        db.commit()
    finally:
        db.close()


def build_subscription_payload(subscription, plan, event: str) -> dict:
    return {
        "event": event,
        "created": utcnow().isoformat(),
        "data": {
            "id": subscription.id,
            "status": subscription.status,
            "customer_name": subscription.customer_name,
            "customer_email": subscription.customer_email,
            "customer_ref": subscription.customer_ref,
            "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "amount": float(plan.amount),
                "interval_unit": plan.interval_unit,
                "interval_count": plan.interval_count,
            } if plan else None,
        },
    }


def enqueue_subscription_event(db: Session, subscription, merchant: Merchant, event: str) -> WebhookDelivery | None:
    """Create a delivery row for a subscription event. Returns None if no webhook URL.

    Events: subscription.activated | subscription.renewed | subscription.canceled | subscription.expired
    """
    if not merchant.webhook_url:
        return None
    from .models import Plan

    plan = db.get(Plan, subscription.plan_id)
    payload = build_subscription_payload(subscription, plan, event)
    delivery = WebhookDelivery(
        merchant_id=merchant.id,
        charge_id=subscription.id,  # related-object id (subscription, not a charge)
        event=event,
        url=merchant.webhook_url,
        payload=payload,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def enqueue_charge_event(
    db: Session, charge: Charge, merchant: Merchant, event: str
) -> WebhookDelivery | None:
    """Create a delivery row for a charge event. Returns None if no webhook URL set.

    Events: charge.paid | charge.refunded | charge.canceled
    """
    if not merchant.webhook_url:
        return None
    payload = build_charge_payload(charge, event)
    delivery = WebhookDelivery(
        merchant_id=merchant.id,
        charge_id=charge.id,
        event=event,
        url=merchant.webhook_url,
        payload=payload,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery
