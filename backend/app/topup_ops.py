"""Merchant prepaid top-up: create intents with a unique amount, capture the
incoming transfer (auto via bank notification, or by slip) and credit balance.
"""

import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Merchant, Topup, WalletEntry, utcnow
from .promptpay import build_payload
from .settings_store import PLATFORM_PROMPTPAY, get_str

AMOUNT_TOLERANCE = 0.001
TOPUP_TTL_MINUTES = 30


def _unique_pay_amount(db: Session, base: float) -> float:
    """base + a random 1–99 satang suffix not used by any pending top-up."""
    for _ in range(80):
        cand = round(base + (secrets.randbelow(99) + 1) / 100, 2)
        clash = (
            db.query(Topup)
            .filter(
                Topup.status == "pending",
                func.abs(Topup.pay_amount - cand) <= AMOUNT_TOLERANCE,
            )
            .first()
        )
        if not clash:
            return cand
    raise HTTPException(status.HTTP_409_CONFLICT, "Could not allocate a unique amount; try again")


def create_topup(db: Session, merchant: Merchant, amount: float) -> Topup:
    platform_pp = get_str(db, PLATFORM_PROMPTPAY)
    if not platform_pp:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Top-up is unavailable — the platform PromptPay account is not configured yet.",
        )
    pay_amount = _unique_pay_amount(db, float(amount))
    topup = Topup(
        merchant_id=merchant.id,
        amount=amount,
        pay_amount=pay_amount,
        promptpay_payload=build_payload(platform_pp, pay_amount),
        expires_at=utcnow() + timedelta(minutes=TOPUP_TTL_MINUTES),
    )
    db.add(topup)
    db.commit()
    db.refresh(topup)
    return topup


def expire_if_needed(db: Session, topup: Topup) -> None:
    if topup.status == "pending" and topup.expires_at and topup.expires_at < utcnow():
        topup.status = "expired"
        db.commit()


def complete_topup(db: Session, topup: Topup, *, method: str, trans_ref: str,
                   sender_name: str | None = None) -> Topup:
    """Credit the merchant's balance for a paid top-up. Idempotent per top-up;
    the unique trans_ref blocks the same transfer from crediting twice."""
    if topup.status == "completed":
        return topup
    if topup.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Top-up is {topup.status}")

    merchant = db.get(Merchant, topup.merchant_id)
    new_balance = round(float(merchant.balance or 0) + float(topup.pay_amount), 2)

    topup.status = "completed"
    topup.method = method
    topup.trans_ref = trans_ref
    topup.sender_name = sender_name
    topup.completed_at = utcnow()
    merchant.balance = new_balance
    db.add(WalletEntry(
        merchant_id=merchant.id,
        amount=float(topup.pay_amount),
        type="topup",
        balance_after=new_balance,
        topup_id=topup.id,
        description=f"เติมเงิน ({method})",
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This transfer was already credited.")
    db.refresh(topup)
    return topup


def cancel_topup(db: Session, topup: Topup) -> Topup:
    if topup.status == "canceled":
        return topup
    if topup.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"ยกเลิกไม่ได้ — รายการ {topup.status} แล้ว")
    topup.status = "canceled"
    db.commit()
    db.refresh(topup)
    return topup


def match_incoming(db: Session, amount: float) -> Topup | None:
    """Find the single pending, non-expired top-up whose unique pay_amount equals
    the credited amount."""
    now = utcnow()
    return (
        db.query(Topup)
        .filter(
            Topup.status == "pending",
            func.abs(Topup.pay_amount - amount) <= AMOUNT_TOLERANCE,
            (Topup.expires_at.is_(None)) | (Topup.expires_at >= now),
        )
        .order_by(Topup.created_at.asc())
        .first()
    )
