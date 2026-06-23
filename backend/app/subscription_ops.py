"""Membership/subscription lifecycle.

PromptPay can't auto-charge a saved card, so "recurring" means: each cycle we issue
an invoice (a Charge with a PromptPay QR); when the member pays it (via the normal
checkout/slip flow) the subscription period advances. Renewals are issued by
`generate_due_invoices` (run manually or on a schedule).
"""

import calendar
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .charge_ops import resolve_promptpay
from .models import Charge, Coupon, Merchant, Plan, Subscription, utcnow
from .notifications import notify_invoice_issued, notify_payment_received
from .promptpay import build_payload


def apply_coupon(amount: float, coupon: Coupon) -> float:
    if coupon.discount_type == "percent":
        amount = amount * (1 - float(coupon.value) / 100)
    else:  # fixed
        amount = amount - float(coupon.value)
    return max(0.0, round(amount, 2))


def add_interval(dt: datetime, unit: str, count: int) -> datetime:
    if unit == "day":
        return dt + timedelta(days=count)
    if unit == "month":
        m = dt.month - 1 + count
        year = dt.year + m // 12
        month = m % 12 + 1
        day = min(dt.day, calendar.monthrange(year, month)[1])
        return dt.replace(year=year, month=month, day=day)
    if unit == "year":
        try:
            return dt.replace(year=dt.year + count)
        except ValueError:  # Feb 29 -> Feb 28
            return dt.replace(year=dt.year + count, day=28)
    raise ValueError(f"unknown interval unit: {unit}")


def _create_invoice(
    db: Session, merchant: Merchant, subscription: Subscription, plan: Plan,
    *, is_first: bool = False, proration: bool = False, amount: float | None = None,
    description: str | None = None,
) -> Charge:
    base = float(plan.amount) if amount is None else float(amount)
    extra = {"subscription_id": subscription.id, "plan_id": plan.id}

    if proration:
        extra["proration"] = True
    elif subscription.coupon_id:
        coupon = db.get(Coupon, subscription.coupon_id)
        if coupon and (coupon.duration == "forever" or is_first):
            base = apply_coupon(base, coupon)
            extra["coupon"] = coupon.code

    base = round(base, 2)
    promptpay_id, account_id = resolve_promptpay(db, merchant, None)
    charge = Charge(
        merchant_id=merchant.id,
        amount=base,
        description=description or f"ค่าสมาชิก: {plan.name}",
        reference=subscription.customer_ref,
        receiving_account_id=account_id,
        subscription_id=subscription.id,
        promptpay_payload=build_payload(promptpay_id, base),
        extra=extra,
    )
    db.add(charge)
    db.commit()
    db.refresh(charge)
    notify_invoice_issued(db, subscription, charge, merchant.business_name)
    return charge


def open_invoice(db: Session, subscription: Subscription) -> Charge | None:
    """The latest still-pending invoice for a subscription, if any."""
    return (
        db.query(Charge)
        .filter(Charge.subscription_id == subscription.id, Charge.status == "pending")
        .order_by(Charge.created_at.desc())
        .first()
    )


def create_subscription(db: Session, merchant: Merchant, plan: Plan, *, customer_name,
                        customer_email=None, customer_phone=None, customer_line_id=None,
                        customer_ref=None, coupon: Coupon | None = None):
    """Create a member subscription (status pending) plus its first invoice."""
    sub = Subscription(
        merchant_id=merchant.id, plan_id=plan.id, customer_name=customer_name,
        customer_email=customer_email, customer_phone=customer_phone,
        customer_line_id=customer_line_id, customer_ref=customer_ref,
        coupon_id=coupon.id if coupon else None, status="pending",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    if coupon:
        coupon.times_redeemed += 1
        db.commit()
    invoice = _create_invoice(db, merchant, sub, plan, is_first=True)
    return sub, invoice


def issue_renewal(db: Session, merchant: Merchant, subscription: Subscription) -> Charge:
    """Issue the next invoice and mark the subscription past_due until it is paid."""
    if subscription.status == "canceled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Subscription is canceled")
    existing = open_invoice(db, subscription)
    if existing:
        return existing  # don't double-invoice
    plan = db.get(Plan, subscription.plan_id)
    invoice = _create_invoice(db, merchant, subscription, plan)
    if subscription.status == "active":
        subscription.status = "past_due"
        db.commit()
    return invoice


def advance_on_payment(db: Session, charge: Charge) -> str | None:
    """Called after a subscription invoice charge is paid: activate / extend the period.

    Returns the webhook event that occurred (subscription.activated / .renewed) or None.
    """
    if not charge.subscription_id:
        return None
    sub = db.get(Subscription, charge.subscription_id)
    if not sub or sub.status == "canceled":
        return None
    merchant = db.get(Merchant, sub.merchant_id)
    # Proration adjustments don't extend the period (the plan already switched).
    if charge.extra and charge.extra.get("proration"):
        notify_payment_received(db, sub, charge, merchant.business_name)
        return None
    plan = db.get(Plan, sub.plan_id)
    paid_at = charge.paid_at or utcnow()
    first_activation = sub.current_period_start is None
    # Extend from the later of now or the current period end (so early renewals stack).
    base = sub.current_period_end if (sub.current_period_end and sub.current_period_end > paid_at) else paid_at
    if first_activation:
        sub.current_period_start = paid_at
    sub.current_period_end = add_interval(base, plan.interval_unit, plan.interval_count)
    sub.status = "active"
    db.commit()
    notify_payment_received(db, sub, charge, merchant.business_name)
    return "subscription.activated" if first_activation else "subscription.renewed"


def change_plan(db: Session, merchant: Merchant, subscription: Subscription, new_plan: Plan):
    """Switch a member to a new plan, prorating the difference for the remaining period.

    Returns (subscription, proration_invoice_or_None).
    """
    if subscription.status in ("canceled", "expired"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot change plan of a {subscription.status} membership")
    if new_plan.id == subscription.plan_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Already on this plan")

    old_plan = db.get(Plan, subscription.plan_id)

    # Not active yet: just swap the plan and reissue the pending invoice at the new price.
    if subscription.status == "pending" or not subscription.current_period_start:
        subscription.plan_id = new_plan.id
        db.commit()
        existing = open_invoice(db, subscription)
        if existing:
            existing.status = "canceled"
            existing.canceled_at = utcnow()
            db.commit()
        return subscription, _create_invoice(db, merchant, subscription, new_plan, is_first=True)

    # Active/past_due: prorate the remaining time.
    now = utcnow()
    start, end = subscription.current_period_start, subscription.current_period_end
    total = (end - start).total_seconds() if (start and end) else 0
    remaining = max(0.0, (end - now).total_seconds()) if end else 0.0
    frac = (remaining / total) if total > 0 else 0.0
    delta = round(float(new_plan.amount) * frac - float(old_plan.amount) * frac, 2)

    subscription.plan_id = new_plan.id
    db.commit()

    if delta > 0.005:  # upgrade -> charge the prorated difference now
        invoice = _create_invoice(
            db, merchant, subscription, new_plan, proration=True, amount=delta,
            description=f"ปรับแผนเป็น {new_plan.name} (ส่วนต่างตามสัดส่วน)",
        )
        return subscription, invoice
    return subscription, None  # downgrade -> no charge; new price applies next cycle


def expire_lapsed(db: Session, merchant: Merchant, grace_days: int) -> list[Subscription]:
    """Mark past_due subscriptions whose period ended more than grace_days ago as expired."""
    cutoff = utcnow() - timedelta(days=grace_days)
    lapsed = (
        db.query(Subscription)
        .filter(
            Subscription.merchant_id == merchant.id,
            Subscription.status == "past_due",
            Subscription.current_period_end.isnot(None),
            Subscription.current_period_end < cutoff,
        )
        .all()
    )
    now = utcnow()
    for sub in lapsed:
        sub.status = "expired"
        sub.ended_at = now
    if lapsed:
        db.commit()
    return lapsed


def cancel_subscription(db: Session, subscription: Subscription) -> Subscription:
    if subscription.status == "canceled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already canceled")
    now = utcnow()
    subscription.status = "canceled"
    subscription.canceled_at = now
    subscription.ended_at = now
    db.commit()
    db.refresh(subscription)
    return subscription


def monthly_amount(plan: Plan) -> float:
    """Normalize a plan's price to a monthly figure for MRR."""
    amt = float(plan.amount)
    n = plan.interval_count or 1
    if plan.interval_unit == "month":
        return amt / n
    if plan.interval_unit == "year":
        return amt / (12 * n)
    if plan.interval_unit == "day":
        return amt * 30.4375 / n
    return amt


def subscription_stats(db: Session, merchant: Merchant) -> dict:
    """MRR / churn / membership counts for a merchant."""
    subs = db.query(Subscription).filter(Subscription.merchant_id == merchant.id).all()
    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    by_status = {k: 0 for k in ("pending", "active", "past_due", "expired", "canceled")}
    mrr = 0.0
    new_this_month = 0
    churned_this_month = 0
    plan_cache: dict[str, Plan] = {}

    for s in subs:
        by_status[s.status] = by_status.get(s.status, 0) + 1
        if s.status == "active":
            plan = plan_cache.get(s.plan_id) or db.get(Plan, s.plan_id)
            plan_cache[s.plan_id] = plan
            mrr += monthly_amount(plan)
        if s.current_period_start and s.current_period_start >= month_start:
            new_this_month += 1
        if s.ended_at and s.ended_at >= month_start:
            churned_this_month += 1

    active = by_status["active"]
    churn_rate = round(churned_this_month / max(1, active + churned_this_month) * 100, 1)
    return {
        "active_members": active,
        "mrr": round(mrr, 2),
        "arr": round(mrr * 12, 2),
        "new_this_month": new_this_month,
        "churned_this_month": churned_this_month,
        "churn_rate": churn_rate,
        "by_status": by_status,
    }


def generate_due_invoices(db: Session, merchant: Merchant, grace_days: int = 0) -> list[Charge]:
    """Issue renewal invoices for active subscriptions whose period has ended."""
    cutoff = utcnow() - timedelta(days=grace_days)
    due = (
        db.query(Subscription)
        .filter(
            Subscription.merchant_id == merchant.id,
            Subscription.status == "active",
            Subscription.current_period_end.isnot(None),
            Subscription.current_period_end <= cutoff,
        )
        .all()
    )
    invoices = []
    for sub in due:
        if not open_invoice(db, sub):
            invoices.append(issue_renewal(db, merchant, sub))
    return invoices
