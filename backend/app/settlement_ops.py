"""Settlement batching: group unsettled paid charges into a payout statement."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Charge, Merchant, Settlement, utcnow


def unsettled_paid_charges(
    db: Session, merchant: Merchant, start: datetime | None, end: datetime | None
) -> list[Charge]:
    q = db.query(Charge).filter(
        Charge.merchant_id == merchant.id,
        Charge.status == "paid",
        Charge.settlement_id.is_(None),
    )
    if start:
        q = q.filter(Charge.paid_at >= start)
    if end:
        q = q.filter(Charge.paid_at <= end)
    return q.order_by(Charge.paid_at.asc()).all()


def generate_settlement(
    db: Session, merchant: Merchant, start: datetime | None, end: datetime | None
) -> Settlement:
    charges = unsettled_paid_charges(db, merchant, start, end)
    if not charges:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No unsettled paid charges to settle")

    gross = sum(float(c.amount) for c in charges)
    count = len(charges)
    pct = float(merchant.fee_percent or 0)
    fixed = float(merchant.fee_fixed or 0)
    fee = round(gross * pct / 100 + fixed * count, 2)
    net = round(gross - fee, 2)

    paid_times = [c.paid_at for c in charges if c.paid_at]
    settlement = Settlement(
        merchant_id=merchant.id,
        period_start=start or (min(paid_times) if paid_times else None),
        period_end=end or (max(paid_times) if paid_times else None),
        gross_amount=round(gross, 2),
        fee_amount=fee,
        net_amount=net,
        charge_count=count,
        status="pending",
    )
    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    for c in charges:
        c.settlement_id = settlement.id
    db.commit()
    return settlement


def mark_paid_out(db: Session, settlement: Settlement, reference: str | None) -> Settlement:
    if settlement.status == "paid_out":
        raise HTTPException(status.HTTP_409_CONFLICT, "Settlement already paid out")
    settlement.status = "paid_out"
    settlement.reference = reference
    settlement.paid_out_at = utcnow()
    db.commit()
    db.refresh(settlement)
    return settlement
