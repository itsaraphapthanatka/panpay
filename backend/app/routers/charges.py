from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from .. import audit
from ..charge_ops import create_charge, refund_charge, void_charge
from ..database import get_db
from ..deps import get_api_merchant
from ..models import Charge, Merchant, utcnow
from ..ratelimit import limit_api
from ..schemas import ChargeCreate, ChargeOut, RefundRequest
from ..serializers import charge_to_out
from ..webhooks import deliver_webhook, enqueue_charge_event

router = APIRouter(prefix="/v1/charges", tags=["charges (api)"], dependencies=[Depends(limit_api)])


def _fire(background: BackgroundTasks, db: Session, charge: Charge, merchant: Merchant, event: str):
    delivery = enqueue_charge_event(db, charge, merchant, event)
    if delivery:
        background.add_task(deliver_webhook, delivery.id, merchant.webhook_secret)


def _get_owned(db: Session, charge_id: str, merchant: Merchant) -> Charge:
    charge = db.get(Charge, charge_id)
    if not charge or charge.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charge not found")
    return charge


@router.post("", response_model=ChargeOut, status_code=status.HTTP_201_CREATED)
def create(
    body: ChargeCreate,
    request: Request,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    charge = create_charge(db, merchant, body)
    audit.record(db, action="charge.create", actor="api", merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request,
                 extra={"amount": float(charge.amount)})
    return charge_to_out(charge)


@router.get("", response_model=list[ChargeOut])
def list_charges(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    q = db.query(Charge).filter(Charge.merchant_id == merchant.id)
    if status_filter:
        q = q.filter(Charge.status == status_filter)
    charges = q.order_by(Charge.created_at.desc()).limit(limit).all()
    return [charge_to_out(c) for c in charges]


@router.get("/{charge_id}", response_model=ChargeOut)
def get_charge(
    charge_id: str,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    charge = _get_owned(db, charge_id, merchant)
    _expire_if_needed(db, charge)
    return charge_to_out(charge)


@router.post("/{charge_id}/void", response_model=ChargeOut)
def void(
    charge_id: str,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    charge = _get_owned(db, charge_id, merchant)
    _expire_if_needed(db, charge)
    charge = void_charge(db, charge)
    audit.record(db, action="charge.void", actor="api", merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request)
    _fire(background, db, charge, merchant, "charge.canceled")
    return charge_to_out(charge)


@router.post("/{charge_id}/refund", response_model=ChargeOut)
def refund(
    charge_id: str,
    body: RefundRequest,
    request: Request,
    background: BackgroundTasks,
    merchant: Merchant = Depends(get_api_merchant),
    db: Session = Depends(get_db),
):
    charge = _get_owned(db, charge_id, merchant)
    charge = refund_charge(db, charge, body.reason)
    audit.record(db, action="charge.refund", actor="api", merchant_id=merchant.id,
                 target_type="charge", target_id=charge.id, request=request,
                 extra={"reason": body.reason})
    _fire(background, db, charge, merchant, "charge.refunded")
    return charge_to_out(charge)


def _expire_if_needed(db: Session, charge: Charge) -> None:
    if charge.status == "pending" and charge.expires_at and charge.expires_at < utcnow():
        charge.status = "expired"
        db.commit()
