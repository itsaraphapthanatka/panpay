"""Prepaid usage billing: charge merchant credit per processed transaction.

Rate resolution: a merchant's own credit_per_transaction overrides the global
setting (default 0.5). A merchant must hold at least one transaction's worth of
credit to create a new charge; the credit is deducted when the charge settles.
"""

from fastapi import HTTPException, status
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
    """Block creating a new transaction when the merchant is out of credit."""
    rate = credit_rate(db, merchant)
    if rate > 0 and float(merchant.balance or 0) < rate:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            f"เครดิตไม่พอ (ต้องมีอย่างน้อย {rate:.2f} บาทต่อรายการ) กรุณาเติมเงิน",
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
