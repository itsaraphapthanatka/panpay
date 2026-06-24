"""Admin-side membership management, scoped to a specific merchant.

Mirrors the merchant-facing /dashboard membership endpoints, but authenticated
as a platform admin and targeting any merchant by id. Reuses the same
subscription_ops business logic.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..deps import get_current_admin
from ..models import AdminUser, Charge, Coupon, Merchant, NotificationLog, Plan, Subscription, utcnow
from ..schemas import (
    ChangePlanRequest,
    ChargeOut,
    CouponCreate,
    CouponOut,
    NotificationLogOut,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    SubscriptionCreate,
    SubscriptionCreated,
    SubscriptionDetail,
    SubscriptionOut,
    SubscriptionStats,
)
from ..serializers import charge_to_out, subscription_to_out
from ..subscription_ops import (
    cancel_subscription,
    change_plan,
    create_subscription,
    generate_due_invoices,
    issue_renewal,
    subscription_stats,
)
from ..webhooks import deliver_webhook, enqueue_subscription_event

router = APIRouter(prefix="/admin/merchants/{merchant_id}", tags=["admin-membership"])


def target_merchant(
    merchant_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> Merchant:
    """Resolve the merchant being managed; admin auth is enforced here."""
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return merchant


def _get_plan(db: Session, plan_id: str, merchant: Merchant) -> Plan:
    plan = db.get(Plan, plan_id)
    if not plan or plan.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    return plan


def _get_sub(db: Session, sub_id: str, merchant: Merchant) -> Subscription:
    sub = db.get(Subscription, sub_id)
    if not sub or sub.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    return sub


def _validate_coupon(db: Session, merchant: Merchant, code: str) -> Coupon:
    c = db.query(Coupon).filter(Coupon.merchant_id == merchant.id, Coupon.code == code).first()
    if not c or not c.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid coupon code")
    if c.expires_at and c.expires_at < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Coupon has expired")
    if c.max_redemptions is not None and c.times_redeemed >= c.max_redemptions:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Coupon fully redeemed")
    return c


# ---- Plans ----
@router.get("/plans", response_model=list[PlanOut])
def list_plans(merchant: Merchant = Depends(target_merchant), db: Session = Depends(get_db)):
    return (
        db.query(Plan).filter(Plan.merchant_id == merchant.id).order_by(Plan.created_at.desc()).all()
    )


@router.post("/plans", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    plan = Plan(
        merchant_id=merchant.id, name=body.name, amount=body.amount,
        interval_unit=body.interval_unit, interval_count=body.interval_count,
        description=body.description,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    audit.record(db, action="plan.create", actor=admin.email, merchant_id=merchant.id,
                 target_type="plan", target_id=plan.id, request=request, extra={"via": "admin"})
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: str,
    body: PlanUpdate,
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    plan = _get_plan(db, plan_id, merchant)
    if body.name is not None:
        plan.name = body.name
    if body.active is not None:
        plan.active = body.active
    if body.description is not None:
        plan.description = body.description
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(
    plan_id: str,
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    plan = _get_plan(db, plan_id, merchant)
    in_use = db.query(Subscription).filter(Subscription.plan_id == plan_id).count()
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plan has subscriptions; deactivate it instead")
    db.delete(plan)
    db.commit()


# ---- Subscriptions (members) ----
@router.get("/subscription-stats", response_model=SubscriptionStats)
def stats(merchant: Merchant = Depends(target_merchant), db: Session = Depends(get_db)):
    return subscription_stats(db, merchant)


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def list_subscriptions(
    status_filter: str | None = Query(default=None, alias="status"),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    q = db.query(Subscription).filter(Subscription.merchant_id == merchant.id)
    if status_filter:
        q = q.filter(Subscription.status == status_filter)
    subs = q.order_by(Subscription.created_at.desc()).all()
    return [subscription_to_out(s) for s in subs]


@router.post("/subscriptions", response_model=SubscriptionCreated, status_code=status.HTTP_201_CREATED)
def create_sub(
    body: SubscriptionCreate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    plan = _get_plan(db, body.plan_id, merchant)
    if not plan.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Plan is inactive")
    coupon = _validate_coupon(db, merchant, body.coupon_code) if body.coupon_code else None
    sub, invoice = create_subscription(
        db, merchant, plan,
        customer_name=body.customer_name, customer_email=body.customer_email,
        customer_phone=body.customer_phone, customer_line_id=body.customer_line_id,
        customer_ref=body.customer_ref, coupon=coupon,
    )
    audit.record(db, action="subscription.create", actor=admin.email, merchant_id=merchant.id,
                 target_type="subscription", target_id=sub.id, request=request, extra={"via": "admin"})
    return SubscriptionCreated(subscription=subscription_to_out(sub), invoice=charge_to_out(invoice))


@router.post("/subscriptions/{sub_id}/change-plan", response_model=SubscriptionDetail)
def change_sub_plan(
    sub_id: str,
    body: ChangePlanRequest,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    sub = _get_sub(db, sub_id, merchant)
    new_plan = _get_plan(db, body.plan_id, merchant)
    sub, _invoice = change_plan(db, merchant, sub, new_plan)
    audit.record(db, action="subscription.change_plan", actor=admin.email, merchant_id=merchant.id,
                 target_type="subscription", target_id=sub.id, request=request,
                 extra={"plan_id": new_plan.id, "via": "admin"})
    invoices = (
        db.query(Charge).filter(Charge.subscription_id == sub.id).order_by(Charge.created_at.desc()).all()
    )
    return SubscriptionDetail(subscription=subscription_to_out(sub), invoices=[charge_to_out(c) for c in invoices])


@router.get("/subscriptions/{sub_id}", response_model=SubscriptionDetail)
def get_sub(sub_id: str, merchant: Merchant = Depends(target_merchant), db: Session = Depends(get_db)):
    sub = _get_sub(db, sub_id, merchant)
    invoices = (
        db.query(Charge).filter(Charge.subscription_id == sub.id).order_by(Charge.created_at.desc()).all()
    )
    return SubscriptionDetail(
        subscription=subscription_to_out(sub),
        invoices=[charge_to_out(c) for c in invoices],
    )


@router.post("/subscriptions/{sub_id}/invoice", response_model=ChargeOut)
def renew(sub_id: str, merchant: Merchant = Depends(target_merchant), db: Session = Depends(get_db)):
    sub = _get_sub(db, sub_id, merchant)
    invoice = issue_renewal(db, merchant, sub)
    return charge_to_out(invoice)


@router.post("/subscriptions/{sub_id}/cancel", response_model=SubscriptionOut)
def cancel(
    sub_id: str,
    request: Request,
    background: BackgroundTasks,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    sub = cancel_subscription(db, _get_sub(db, sub_id, merchant))
    audit.record(db, action="subscription.cancel", actor=admin.email, merchant_id=merchant.id,
                 target_type="subscription", target_id=sub.id, request=request, extra={"via": "admin"})
    delivery = enqueue_subscription_event(db, sub, merchant, "subscription.canceled")
    if delivery:
        background.add_task(deliver_webhook, delivery.id, merchant.webhook_secret)
    return subscription_to_out(sub)


@router.post("/subscriptions/generate-due", response_model=list[ChargeOut])
def generate_due(
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    invoices = generate_due_invoices(db, merchant)
    audit.record(db, action="subscription.generate_due", actor=admin.email, merchant_id=merchant.id,
                 request=request, extra={"count": len(invoices), "via": "admin"})
    return [charge_to_out(c) for c in invoices]


# ---- Coupons ----
@router.get("/coupons", response_model=list[CouponOut])
def list_coupons(merchant: Merchant = Depends(target_merchant), db: Session = Depends(get_db)):
    return (
        db.query(Coupon).filter(Coupon.merchant_id == merchant.id).order_by(Coupon.created_at.desc()).all()
    )


@router.post("/coupons", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
def create_coupon(
    body: CouponCreate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    if body.discount_type == "percent" and body.value > 100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Percent discount cannot exceed 100")
    exists = db.query(Coupon).filter(Coupon.merchant_id == merchant.id, Coupon.code == body.code).first()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Coupon code already exists")
    coupon = Coupon(
        merchant_id=merchant.id, code=body.code, discount_type=body.discount_type, value=body.value,
        duration=body.duration, max_redemptions=body.max_redemptions, expires_at=body.expires_at,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    audit.record(db, action="coupon.create", actor=admin.email, merchant_id=merchant.id,
                 target_type="coupon", target_id=coupon.id, request=request, extra={"via": "admin"})
    return coupon


@router.delete("/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: str,
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    coupon = db.get(Coupon, coupon_id)
    if not coupon or coupon.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coupon not found")
    coupon.active = False  # soft-disable so historical redemptions stay intact
    db.commit()


# ---- Notifications ----
@router.get("/notifications", response_model=list[NotificationLogOut])
def list_notifications(
    limit: int = Query(default=100, le=500),
    merchant: Merchant = Depends(target_merchant),
    db: Session = Depends(get_db),
):
    return (
        db.query(NotificationLog)
        .filter(NotificationLog.merchant_id == merchant.id)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )
