"""Prepaid usage billing: charge merchant credit per processed transaction.

Rate resolution: a merchant's own credit_per_transaction overrides the global
setting (default 0.5). A merchant must hold at least one transaction's worth of
credit to create a new charge; the credit is deducted when the charge settles.
"""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Charge, Merchant, WalletEntry
from .settings_store import CREDIT_PER_TRANSACTION, DEFAULT_CREDIT_PER_TRANSACTION, get_str


def credit_rate(db: Session, merchant: Merchant) -> float:
    if merchant.credit_per_transaction is not None:
        return float(merchant.credit_per_transaction)
    try:
        return float(get_str(db, CREDIT_PER_TRANSACTION, DEFAULT_CREDIT_PER_TRANSACTION))
    except (TypeError, ValueError):
        return float(DEFAULT_CREDIT_PER_TRANSACTION)


def ensure_credit(db: Session, merchant: Merchant) -> None:
    """Block creating a new transaction unless the merchant holds enough credit to
    cover every still-pending charge plus this one. Without counting outstanding
    pending charges, a merchant with one transaction's credit could create
    unlimited charges and drive the balance negative when they all settle."""
    rate = credit_rate(db, merchant)
    if rate <= 0:
        return
    pending = (
        db.query(func.count(Charge.id))
        .filter(Charge.merchant_id == merchant.id, Charge.status == "pending")
        .scalar()
        or 0
    )
    required = round(rate * (pending + 1), 2)
    if float(merchant.balance or 0) < required:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"เครดิตไม่พอ — มีรายการรอชำระ {pending} รายการ ต้องมีเครดิต ≥ {required:.2f} บาท "
            f"(หักรายการละ {rate:.2f}) กรุณาเติมเงิน",
        )


def charge_usage(db: Session, merchant: Merchant, charge: Charge) -> None:
    """Deduct one transaction's credit and append a ledger debit. The caller
    commits (so this is atomic with settling the payment)."""
    rate = credit_rate(db, merchant)
    if rate <= 0:
        return
    new_balance = round(float(merchant.balance or 0) - rate, 2)
    merchant.balance = new_balance
    db.add(WalletEntry(
        merchant_id=merchant.id,
        amount=-rate,
        type="usage",
        balance_after=new_balance,
        topup_id=None,
        description=f"ค่าบริการต่อรายการ (charge {charge.id})",
    ))


def refund_usage(db: Session, merchant: Merchant, charge: Charge) -> None:
    """Give back the per-transaction credit when a paid charge is refunded.
    Refunds the exact amount that was charged at settle (rate may have changed
    since). No-op if nothing was charged or it was already refunded. The caller
    commits (atomic with the refund)."""
    usage = (
        db.query(WalletEntry)
        .filter(
            WalletEntry.merchant_id == merchant.id,
            WalletEntry.type == "usage",
            WalletEntry.description.like(f"%{charge.id}%"),
        )
        .first()
    )
    if not usage:
        return
    already = (
        db.query(WalletEntry)
        .filter(
            WalletEntry.merchant_id == merchant.id,
            WalletEntry.type == "usage_refund",
            WalletEntry.description.like(f"%{charge.id}%"),
        )
        .first()
    )
    if already:
        return
    amount = abs(float(usage.amount))
    if amount <= 0:
        return
    new_balance = round(float(merchant.balance or 0) + amount, 2)
    merchant.balance = new_balance
    db.add(WalletEntry(
        merchant_id=merchant.id,
        amount=amount,
        type="usage_refund",
        balance_after=new_balance,
        topup_id=None,
        description=f"คืนค่าบริการ (refund charge {charge.id})",
    ))
