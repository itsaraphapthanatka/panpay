from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import audit
from ..charge_ops import create_charge as _create_charge
from ..charge_ops import refund_charge, void_charge
from ..database import get_db
from ..deps import get_current_merchant
from ..models import ApiKey, AuditLog, Charge, Merchant, ReceivingAccount, Settlement, utcnow
from ..reports import charges_csv, settlement_csv
from ..schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyOut,
    AuditLogOut,
    ChargeCreate,
    ChargeOut,
    DashboardStats,
    MerchantOut,
    MerchantSettingsUpdate,
    PayoutRequest,
    ReceivingAccountCreate,
    ReceivingAccountOut,
    RefundRequest,
    SettlementGenerate,
    SettlementOut,
)
from ..security import generate_api_key
from ..serializers import charge_to_out
from ..settlement_ops import generate_settlement, mark_paid_out
from ..webhooks import deliver_webhook, enqueue_charge_event


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _get_owned(db: Session, charge_id: str, merchant: Merchant) -> Charge:
    charge = db.get(Charge, charge_id)
    if not charge or charge.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charge not found")
    return charge


def _fire(background: BackgroundTasks, db: Session, charge: Charge, merchant: Merchant, event: str):
    delivery = enqueue_charge_event(db, charge, merchant, event)
    if delivery:
        background.add_task(deliver_webhook, delivery.id, merchant.webhook_secret)


# ---- Settings ----
@router.patch("/settings", response_model=MerchantOut)
def update_settings(
    body: MerchantSettingsUpdate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    if body.business_name is not None:
        merchant.business_name = body.business_name
    if body.promptpay_id is not None:
        merchant.promptpay_id = body.promptpay_id
    if body.webhook_url is not None:
        merchant.webhook_url = body.webhook_url or None
    if body.fee_percent is not None:
        merchant.fee_percent = body.fee_percent
    if body.fee_fixed is not None:
        merchant.fee_fixed = body.fee_fixed
    db.commit()
    db.refresh(merchant)
    audit.record(db, action="settings.update", actor=merchant.email, merchant_id=merchant.id,
                 request=request)
    return merchant


# ---- API keys ----
@router.get("/api-keys", response_model=list[ApiKeyOut])
def list_api_keys(
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return (
        db.query(ApiKey)
        .filter(ApiKey.merchant_id == merchant.id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    body: ApiKeyCreate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    full, secret_hash, prefix, last_four = generate_api_key()
    key = ApiKey(merchant_id=merchant.id, name=body.name, secret_hash=secret_hash,
                 prefix=prefix, last_four=last_four)
    db.add(key)
    db.commit()
    db.refresh(key)
    audit.record(db, action="api_key.create", actor=merchant.email, merchant_id=merchant.id,
                 target_type="api_key", target_id=key.id, request=request)
    return ApiKeyCreated(
        id=key.id, name=key.name, prefix=key.prefix, last_four=key.last_four,
        revoked=key.revoked, created_at=key.created_at, last_used_at=key.last_used_at, secret=full,
    )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: str,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    key = db.get(ApiKey, key_id)
    if not key or key.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    key.revoked = True
    db.commit()
    audit.record(db, action="api_key.revoke", actor=merchant.email, merchant_id=merchant.id,
                 target_type="api_key", target_id=key.id, request=request)


# ---- Receiving accounts ----
@router.get("/receiving-accounts", response_model=list[ReceivingAccountOut])
def list_accounts(
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return (
        db.query(ReceivingAccount)
        .filter(ReceivingAccount.merchant_id == merchant.id)
        .order_by(ReceivingAccount.is_default.desc(), ReceivingAccount.created_at.desc())
        .all()
    )


@router.post("/receiving-accounts", response_model=ReceivingAccountOut, status_code=status.HTTP_201_CREATED)
def create_account(
    body: ReceivingAccountCreate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    acct = ReceivingAccount(
        merchant_id=merchant.id, name=body.name, promptpay_id=body.promptpay_id,
        is_default=body.is_default,
    )
    # First account is default; enforce single default.
    existing = db.query(ReceivingAccount).filter(ReceivingAccount.merchant_id == merchant.id).count()
    if existing == 0:
        acct.is_default = True
    if acct.is_default:
        for other in db.query(ReceivingAccount).filter(ReceivingAccount.merchant_id == merchant.id):
            other.is_default = False
    db.add(acct)
    db.commit()
    db.refresh(acct)
    audit.record(db, action="receiving_account.create", actor=merchant.email, merchant_id=merchant.id,
                 target_type="receiving_account", target_id=acct.id, request=request)
    return acct


@router.post("/receiving-accounts/{account_id}/default", response_model=ReceivingAccountOut)
def set_default_account(
    account_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    acct = db.get(ReceivingAccount, account_id)
    if not acct or acct.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    for other in db.query(ReceivingAccount).filter(ReceivingAccount.merchant_id == merchant.id):
        other.is_default = other.id == account_id
    db.commit()
    db.refresh(acct)
    return acct


@router.delete("/receiving-accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    acct = db.get(ReceivingAccount, account_id)
    if not acct or acct.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    db.delete(acct)
    db.commit()


# ---- Charges (dashboard view) ----
@router.post("/charges", response_model=ChargeOut, status_code=status.HTTP_201_CREATED)
def create_charge(
    body: ChargeCreate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    charge = _create_charge(db, merchant, body)
    audit.record(db, action="charge.create", actor=merchant.email, merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request,
                 extra={"amount": float(charge.amount)})
    return charge_to_out(charge)


@router.get("/charges", response_model=list[ChargeOut])
def list_charges(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    q = db.query(Charge).options(joinedload(Charge.payment)).filter(Charge.merchant_id == merchant.id)
    if status_filter:
        q = q.filter(Charge.status == status_filter)
    charges = q.order_by(Charge.created_at.desc()).limit(limit).all()
    return [charge_to_out(c) for c in charges]


@router.post("/charges/{charge_id}/void", response_model=ChargeOut)
def void(
    charge_id: str,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    charge = void_charge(db, _get_owned(db, charge_id, merchant))
    audit.record(db, action="charge.void", actor=merchant.email, merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request)
    _fire(background, db, charge, merchant, "charge.canceled")
    return charge_to_out(charge)


@router.post("/charges/{charge_id}/refund", response_model=ChargeOut)
def refund(
    charge_id: str,
    body: RefundRequest,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    charge = refund_charge(db, _get_owned(db, charge_id, merchant), body.reason)
    audit.record(db, action="charge.refund", actor=merchant.email, merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request,
                 extra={"reason": body.reason})
    _fire(background, db, charge, merchant, "charge.refunded")
    return charge_to_out(charge)


# ---- CSV export ----
@router.get("/charges/export.csv")
def export_charges(
    status_filter: str | None = Query(default=None, alias="status"),
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    q = db.query(Charge).options(joinedload(Charge.payment)).filter(Charge.merchant_id == merchant.id)
    if status_filter:
        q = q.filter(Charge.status == status_filter)
    charges = q.order_by(Charge.created_at.desc()).all()
    return _csv_response(charges_csv(charges), "panpay-transactions.csv")


# ---- Settlements / payout ----
@router.get("/settlements", response_model=list[SettlementOut])
def list_settlements(
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return (
        db.query(Settlement)
        .filter(Settlement.merchant_id == merchant.id)
        .order_by(Settlement.created_at.desc())
        .all()
    )


@router.post("/settlements/generate", response_model=SettlementOut, status_code=status.HTTP_201_CREATED)
def generate(
    body: SettlementGenerate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    s = generate_settlement(db, merchant, body.period_start, body.period_end)
    audit.record(db, action="settlement.generate", actor=merchant.email, merchant_id=merchant.id,
                 target_type="settlement", target_id=s.id, request=request,
                 extra={"net": float(s.net_amount), "count": s.charge_count})
    return s


@router.post("/settlements/{settlement_id}/payout", response_model=SettlementOut)
def payout(
    settlement_id: str,
    body: PayoutRequest,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    s = db.get(Settlement, settlement_id)
    if not s or s.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Settlement not found")
    s = mark_paid_out(db, s, body.reference)
    audit.record(db, action="settlement.payout", actor=merchant.email, merchant_id=merchant.id,
                 target_type="settlement", target_id=s.id, request=request,
                 extra={"reference": body.reference})
    return s


@router.get("/settlements/{settlement_id}/export.csv")
def export_settlement(
    settlement_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    s = db.get(Settlement, settlement_id)
    if not s or s.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Settlement not found")
    charges = (
        db.query(Charge)
        .options(joinedload(Charge.payment))
        .filter(Charge.settlement_id == s.id)
        .order_by(Charge.paid_at.asc())
        .all()
    )
    return _csv_response(settlement_csv(s, charges), f"settlement-{s.id}.csv")


# ---- Audit log ----
@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = Query(default=100, le=500),
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    return (
        db.query(AuditLog)
        .filter(AuditLog.merchant_id == merchant.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


# ---- Stats ----
@router.get("/stats", response_model=DashboardStats)
def stats(
    days: int = Query(default=14, ge=1, le=90),
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    now = utcnow()
    since = now - timedelta(days=days)

    charges = (
        db.query(Charge)
        .filter(Charge.merchant_id == merchant.id, Charge.created_at >= since)
        .all()
    )

    paid = [c for c in charges if c.status == "paid"]
    pending = [c for c in charges if c.status == "pending"]
    total_paid_amount = sum(float(c.amount) for c in paid)

    today = now.date()
    today_paid = [c for c in paid if (c.paid_at or c.created_at).date() == today]
    today_amount = sum(float(c.amount) for c in today_paid)

    buckets: dict[str, dict] = {}
    for i in range(days):
        d = (since + timedelta(days=i + 1)).date().isoformat()
        buckets[d] = {"date": d, "amount": 0.0, "count": 0}
    for c in paid:
        d = (c.paid_at or c.created_at).date().isoformat()
        if d in buckets:
            buckets[d]["amount"] += float(c.amount)
            buckets[d]["count"] += 1

    return DashboardStats(
        total_paid_amount=round(total_paid_amount, 2),
        paid_count=len(paid),
        pending_count=len(pending),
        today_amount=round(today_amount, 2),
        today_count=len(today_paid),
        series=list(buckets.values()),
    )
