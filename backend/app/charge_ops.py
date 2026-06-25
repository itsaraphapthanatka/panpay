"""Shared charge lifecycle helpers used by both the API and dashboard routers."""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Charge, Merchant, ReceivingAccount, utcnow
from .promptpay import build_payload


def resolve_promptpay(db: Session, merchant: Merchant, account_id: str | None) -> tuple[str, str | None]:
    """Return (promptpay_id, receiving_account_id) for a new charge.

    Priority: explicit account_id -> merchant's default account -> merchant.promptpay_id.
    """
    if account_id:
        acct = db.get(ReceivingAccount, account_id)
        if not acct or acct.merchant_id != merchant.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown receiving account")
        return acct.promptpay_id, acct.id

    default = (
        db.query(ReceivingAccount)
        .filter(ReceivingAccount.merchant_id == merchant.id, ReceivingAccount.is_default.is_(True))
        .first()
    )
    if default:
        return default.promptpay_id, default.id

    if merchant.promptpay_id:
        return merchant.promptpay_id, None

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "No receiving account configured. Add one in Settings or set a PromptPay ID.",
    )


def create_charge(db: Session, merchant: Merchant, body) -> Charge:
    from .billing import ensure_credit

    ensure_credit(db, merchant)  # block when out of prepaid credit
    promptpay_id, account_id = resolve_promptpay(db, merchant, body.account_id)
    expires_at = utcnow() + timedelta(seconds=body.expires_in) if body.expires_in else None
    charge = Charge(
        merchant_id=merchant.id,
        amount=body.amount,
        description=body.description,
        reference=body.reference,
        extra=body.metadata,
        receiving_account_id=account_id,
        promptpay_payload=build_payload(promptpay_id, body.amount),
        expires_at=expires_at,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    return charge


def settle_charge_paid(
    db: Session,
    background,
    charge: Charge,
    *,
    trans_ref: str,
    amount: float,
    sender_name: str | None = None,
    sender_bank: str | None = None,
    receiver_name: str | None = None,
    receiver_bank: str | None = None,
    transferred_at=None,
    provider: str = "bank",
    raw: dict | None = None,
) -> Charge:
    """Mark a pending charge as paid: record the Payment, flip status, advance any
    subscription, and fire merchant webhooks. Shared by slip verification and the
    bank-notification ingest. Raises 409 if the trans_ref was already used.
    """
    # Lazy imports avoid a circular dependency (subscription_ops imports charge_ops).
    from sqlalchemy.exc import IntegrityError

    from .billing import charge_usage
    from .models import Payment, Subscription
    from .subscription_ops import advance_on_payment
    from .webhooks import deliver_webhook, enqueue_charge_event, enqueue_subscription_event

    payment = Payment(
        charge_id=charge.id,
        trans_ref=trans_ref,
        amount=amount,
        sender_name=sender_name,
        sender_bank=sender_bank,
        receiver_name=receiver_name,
        receiver_bank=receiver_bank,
        transferred_at=transferred_at,
        provider=provider,
        raw=raw or {},
    )
    db.add(payment)
    charge.status = "paid"
    charge.paid_at = utcnow()
    # Deduct the per-transaction credit atomically with settling the payment.
    charge_usage(db, db.get(Merchant, charge.merchant_id), charge)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This transaction reference has already been used for another payment.",
        )
    db.refresh(charge)

    if charge.subscription_id:
        sub_event = advance_on_payment(db, charge)
        if sub_event:
            sub = db.get(Subscription, charge.subscription_id)
            sub_delivery = enqueue_subscription_event(db, sub, charge.merchant, sub_event)
            if sub_delivery:
                background.add_task(deliver_webhook, sub_delivery.id, charge.merchant.webhook_secret)

    delivery = enqueue_charge_event(db, charge, charge.merchant, "charge.paid")
    if delivery:
        background.add_task(deliver_webhook, delivery.id, charge.merchant.webhook_secret)

    return charge


def void_charge(db: Session, charge: Charge) -> Charge:
    if charge.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot void a {charge.status} charge")
    charge.status = "canceled"
    charge.canceled_at = utcnow()
    db.commit()
    db.refresh(charge)
    return charge


def refund_charge(db: Session, charge: Charge, reason: str | None) -> Charge:
    from .billing import refund_usage

    if charge.status != "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot refund a {charge.status} charge")
    charge.status = "refunded"
    charge.refunded_at = utcnow()
    charge.refund_reason = reason
    # Give back the per-transaction credit charged when this charge settled.
    refund_usage(db, db.get(Merchant, charge.merchant_id), charge)
    db.commit()
    db.refresh(charge)
    return charge
