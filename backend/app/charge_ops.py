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


def void_charge(db: Session, charge: Charge) -> Charge:
    if charge.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot void a {charge.status} charge")
    charge.status = "canceled"
    charge.canceled_at = utcnow()
    db.commit()
    db.refresh(charge)
    return charge


def refund_charge(db: Session, charge: Charge, reason: str | None) -> Charge:
    if charge.status != "paid":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot refund a {charge.status} charge")
    charge.status = "refunded"
    charge.refunded_at = utcnow()
    charge.refund_reason = reason
    db.commit()
    db.refresh(charge)
    return charge
