"""Platform admin console — oversight across every merchant on the gateway."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from .. import audit
from ..database import get_db
from ..deps import get_current_admin
from ..models import AdminUser, AuditLog, Charge, Merchant, Settlement, utcnow
from ..ratelimit import limit_auth
from ..schemas import (
    AdminChargeOut,
    AdminMerchantOut,
    AdminMerchantUpdate,
    AdminOut,
    AdminSettlementOut,
    AdminStats,
    AuditLogOut,
    LoginRequest,
    SettlementOut,
    TokenResponse,
)
from ..security import create_access_token, create_admin_token, verify_password
from ..serializers import charge_to_out

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- Auth ----
@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_auth)])
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == body.email).first()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    admin.last_login_at = utcnow()
    db.commit()
    audit.record(db, action="admin.login", actor=admin.email, request=request)
    return TokenResponse(access_token=create_admin_token(admin.id))


@router.get("/me", response_model=AdminOut)
def me(admin: AdminUser = Depends(get_current_admin)):
    return admin


# ---- Per-merchant charge rollups (shared by stats + merchant list) ----
def _merchant_rollups(db: Session) -> dict[str, dict]:
    rows = (
        db.query(
            Charge.merchant_id.label("mid"),
            func.count(Charge.id).label("total"),
            func.coalesce(
                func.sum(case((Charge.status == "paid", Charge.amount), else_=0)), 0
            ).label("paid_amount"),
            func.coalesce(
                func.sum(case((Charge.status == "paid", 1), else_=0)), 0
            ).label("paid_count"),
            func.coalesce(
                func.sum(case((Charge.status == "pending", 1), else_=0)), 0
            ).label("pending_count"),
        )
        .group_by(Charge.merchant_id)
        .all()
    )
    return {
        r.mid: {
            "charge_count": int(r.total),
            "paid_amount": round(float(r.paid_amount), 2),
            "paid_count": int(r.paid_count),
            "pending_count": int(r.pending_count),
        }
        for r in rows
    }


# ---- Platform overview ----
@router.get("/stats", response_model=AdminStats)
def stats(admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)):
    merchant_count = db.query(func.count(Merchant.id)).scalar() or 0
    suspended_count = (
        db.query(func.count(Merchant.id)).filter(Merchant.suspended.is_(True)).scalar() or 0
    )

    rollups = _merchant_rollups(db)
    total_paid_amount = round(sum(r["paid_amount"] for r in rollups.values()), 2)
    paid_count = sum(r["paid_count"] for r in rollups.values())
    pending_count = sum(r["pending_count"] for r in rollups.values())

    today = utcnow().date()
    today_paid = (
        db.query(
            func.coalesce(func.sum(Charge.amount), 0),
            func.count(Charge.id),
        )
        .filter(
            Charge.status == "paid",
            func.coalesce(Charge.paid_at, Charge.created_at) >= today,
        )
        .one()
    )

    total_fee_amount = (
        db.query(func.coalesce(func.sum(Settlement.fee_amount), 0))
        .filter(Settlement.status == "paid_out")
        .scalar()
        or 0
    )

    return AdminStats(
        merchant_count=int(merchant_count),
        suspended_count=int(suspended_count),
        total_paid_amount=total_paid_amount,
        paid_count=paid_count,
        pending_count=pending_count,
        today_amount=round(float(today_paid[0]), 2),
        today_count=int(today_paid[1]),
        total_fee_amount=round(float(total_fee_amount), 2),
    )


# ---- Merchants ----
@router.get("/merchants", response_model=list[AdminMerchantOut])
def list_merchants(
    q: str | None = Query(default=None, description="search email / business name"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(Merchant)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (Merchant.email.ilike(like)) | (Merchant.business_name.ilike(like))
        )
    merchants = query.order_by(Merchant.created_at.desc()).all()
    rollups = _merchant_rollups(db)
    return [_merchant_out(m, rollups.get(m.id, {})) for m in merchants]


@router.get("/merchants/{merchant_id}", response_model=AdminMerchantOut)
def get_merchant(
    merchant_id: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return _merchant_out(merchant, _merchant_rollups(db).get(merchant.id, {}))


@router.patch("/merchants/{merchant_id}", response_model=AdminMerchantOut)
def update_merchant(
    merchant_id: str,
    body: AdminMerchantUpdate,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")

    changes: dict = {}
    if body.fee_percent is not None and float(merchant.fee_percent) != body.fee_percent:
        merchant.fee_percent = body.fee_percent
        changes["fee_percent"] = body.fee_percent
    if body.fee_fixed is not None and float(merchant.fee_fixed) != body.fee_fixed:
        merchant.fee_fixed = body.fee_fixed
        changes["fee_fixed"] = body.fee_fixed
    if body.suspended is not None and merchant.suspended != body.suspended:
        merchant.suspended = body.suspended
        changes["suspended"] = body.suspended

    db.commit()
    db.refresh(merchant)
    if changes:
        audit.record(
            db, action="admin.merchant.update", actor=admin.email, merchant_id=merchant.id,
            target_type="merchant", target_id=merchant.id, request=request, extra=changes,
        )
    return _merchant_out(merchant, _merchant_rollups(db).get(merchant.id, {}))


@router.post("/merchants/{merchant_id}/act-as")
def act_as_merchant(
    merchant_id: str,
    request: Request,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Mint a merchant session token so an admin can manage the merchant's
    dashboard with full merchant privileges. Logged for audit."""
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    if merchant.suspended:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Merchant is suspended — unsuspend before managing"
        )
    audit.record(db, action="admin.act_as", actor=admin.email, merchant_id=merchant.id,
                 target_type="merchant", target_id=merchant.id, request=request)
    return {
        "access_token": create_access_token(merchant.id),
        "token_type": "bearer",
        "merchant_id": merchant.id,
        "business_name": merchant.business_name,
    }


def _merchant_out(merchant: Merchant, roll: dict) -> AdminMerchantOut:
    return AdminMerchantOut(
        id=merchant.id,
        email=merchant.email,
        business_name=merchant.business_name,
        promptpay_id=merchant.promptpay_id,
        suspended=merchant.suspended,
        fee_percent=float(merchant.fee_percent),
        fee_fixed=float(merchant.fee_fixed),
        created_at=merchant.created_at,
        charge_count=roll.get("charge_count", 0),
        paid_count=roll.get("paid_count", 0),
        paid_amount=roll.get("paid_amount", 0),
        pending_count=roll.get("pending_count", 0),
    )


# ---- Charges (across all merchants) ----
@router.get("/charges", response_model=list[AdminChargeOut])
def list_charges(
    merchant_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Charge).options(joinedload(Charge.payment), joinedload(Charge.merchant))
    if merchant_id:
        q = q.filter(Charge.merchant_id == merchant_id)
    if status_filter:
        q = q.filter(Charge.status == status_filter)
    charges = q.order_by(Charge.created_at.desc()).limit(limit).all()
    return [
        AdminChargeOut(
            **charge_to_out(c).model_dump(),
            merchant_id=c.merchant_id,
            business_name=c.merchant.business_name if c.merchant else "—",
        )
        for c in charges
    ]


# ---- Settlements (across all merchants) ----
@router.get("/settlements", response_model=list[AdminSettlementOut])
def list_settlements(
    merchant_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(Settlement)
    if merchant_id:
        q = q.filter(Settlement.merchant_id == merchant_id)
    settlements = q.order_by(Settlement.created_at.desc()).limit(limit).all()
    names = {m.id: m.business_name for m in db.query(Merchant).all()}
    return [
        AdminSettlementOut(
            **SettlementOut.model_validate(s).model_dump(),
            merchant_id=s.merchant_id,
            business_name=names.get(s.merchant_id, "—"),
        )
        for s in settlements
    ]


# ---- Platform-wide audit log ----
@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    merchant_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if merchant_id:
        q = q.filter(AuditLog.merchant_id == merchant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()
