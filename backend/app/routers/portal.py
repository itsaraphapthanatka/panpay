"""Public member self-service portal (token-auth, no login).

A member opens /m/{portal_token} on the frontend, which calls these endpoints to
see their membership status + invoices and to pay the current/next invoice.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Charge, Merchant, Plan, Subscription
from ..ratelimit import limit_slip
from ..schemas import PortalRenewResult, PortalView
from ..serializers import charge_to_out
from ..subscription_ops import issue_renewal, open_invoice

router = APIRouter(prefix="/portal", tags=["portal (public)"])


def _get_sub(db: Session, token: str) -> Subscription:
    sub = db.query(Subscription).filter(Subscription.portal_token == token).first()
    if not sub:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")
    return sub


def _checkout_url(charge: Charge) -> str:
    return f"{settings.checkout_base_url}/pay/{charge.id}"


@router.get("/{token}", response_model=PortalView)
def view(token: str, db: Session = Depends(get_db)):
    sub = _get_sub(db, token)
    plan = db.get(Plan, sub.plan_id)
    merchant = db.get(Merchant, sub.merchant_id)
    invoices = (
        db.query(Charge)
        .filter(Charge.subscription_id == sub.id)
        .order_by(Charge.created_at.desc())
        .all()
    )
    open_inv = open_invoice(db, sub)
    return PortalView(
        business_name=merchant.business_name,
        customer_name=sub.customer_name,
        plan_name=plan.name if plan else None,
        plan_amount=float(plan.amount) if plan else None,
        interval_unit=plan.interval_unit if plan else None,
        interval_count=plan.interval_count if plan else None,
        status=sub.status,
        current_period_end=sub.current_period_end,
        open_invoice_url=_checkout_url(open_inv) if open_inv else None,
        invoices=[charge_to_out(c) for c in invoices],
    )


@router.post("/{token}/renew", response_model=PortalRenewResult, dependencies=[Depends(limit_slip)])
def renew(token: str, db: Session = Depends(get_db)):
    """Return a checkout link for the open invoice, issuing the next one if needed."""
    sub = _get_sub(db, token)
    if sub.status == "canceled":
        raise HTTPException(status.HTTP_409_CONFLICT, "Membership is canceled")
    merchant = db.get(Merchant, sub.merchant_id)
    invoice = issue_renewal(db, merchant, sub)  # returns existing open invoice if any
    return PortalRenewResult(checkout_url=_checkout_url(invoice))
