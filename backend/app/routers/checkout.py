from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Charge, Payment, Subscription, utcnow
from ..pdf_receipt import generate_receipt_pdf
from ..promptpay import payload_to_data_uri
from ..ratelimit import limit_slip
from ..schemas import ChargePublic, PaymentOut
from ..slip_qr import decode_qr
from ..slip_verify import get_verifier
from ..subscription_ops import advance_on_payment
from ..webhooks import deliver_webhook, enqueue_charge_event, enqueue_subscription_event

router = APIRouter(prefix="/checkout", tags=["checkout (public)"])

AMOUNT_TOLERANCE = 0.001


def _expire_if_needed(db: Session, charge: Charge) -> None:
    if charge.status == "pending" and charge.expires_at and charge.expires_at < utcnow():
        charge.status = "expired"
        db.commit()


@router.get("/{charge_id}", response_model=ChargePublic)
def get_checkout(charge_id: str, db: Session = Depends(get_db)):
    charge = db.get(Charge, charge_id)
    if not charge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charge not found")
    _expire_if_needed(db, charge)
    return ChargePublic(
        id=charge.id,
        amount=float(charge.amount),
        currency=charge.currency,
        status=charge.status,
        description=charge.description,
        business_name=charge.merchant.business_name,
        qr_image=payload_to_data_uri(charge.promptpay_payload),
        qr_payload=charge.promptpay_payload,
        expires_at=charge.expires_at,
        paid_at=charge.paid_at,
        payment=PaymentOut.model_validate(charge.payment) if charge.payment else None,
    )


@router.get("/{charge_id}/receipt.pdf")
def receipt(charge_id: str, db: Session = Depends(get_db)):
    charge = db.get(Charge, charge_id)
    if not charge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charge not found")
    if charge.status not in ("paid", "refunded"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Receipt is available after payment")
    pdf = generate_receipt_pdf(charge)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="receipt-{charge.id}.pdf"'},
    )


@router.post("/{charge_id}/slip", response_model=ChargePublic, dependencies=[Depends(limit_slip)])
def submit_slip(
    charge_id: str,
    background: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    trans_ref: str | None = Form(default=None),
    qr_payload: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    charge = db.get(Charge, charge_id)
    if not charge:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Charge not found")

    _expire_if_needed(db, charge)
    if charge.status == "paid":
        # Idempotent: already paid, just return current state.
        return get_checkout(charge_id, db)
    if charge.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Charge is {charge.status}")

    file_bytes = file.file.read() if file else None

    # Auto-read the slip QR from the uploaded image when the client didn't
    # already supply one. The decoded payload uniquely identifies the transfer.
    if file_bytes and not qr_payload:
        qr_payload = decode_qr(file_bytes)

    verifier = get_verifier()
    result = verifier.verify(
        expected_amount=float(charge.amount),
        file_bytes=file_bytes,
        qr_payload=qr_payload,
        trans_ref=trans_ref,
    )

    if not result.success:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Slip verification failed: {result.error or 'unknown'}",
        )

    # Amount must match the charge.
    if result.amount is None or abs(float(result.amount) - float(charge.amount)) > AMOUNT_TOLERANCE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Amount mismatch: slip {result.amount} != charge {float(charge.amount)}",
        )

    payment = Payment(
        charge_id=charge.id,
        trans_ref=result.trans_ref,
        amount=result.amount,
        sender_name=result.sender_name,
        sender_bank=result.sender_bank,
        receiver_name=result.receiver_name,
        receiver_bank=result.receiver_bank,
        transferred_at=result.transferred_at,
        provider=result.provider,
        raw=result.raw,
    )
    db.add(payment)
    charge.status = "paid"
    charge.paid_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        # trans_ref already used -> this slip paid a different charge.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This slip has already been used for another payment.",
        )
    db.refresh(charge)

    # If this charge is a subscription invoice, activate/extend the membership.
    if charge.subscription_id:
        sub_event = advance_on_payment(db, charge)
        if sub_event:
            sub = db.get(Subscription, charge.subscription_id)
            sub_delivery = enqueue_subscription_event(db, sub, charge.merchant, sub_event)
            if sub_delivery:
                background.add_task(deliver_webhook, sub_delivery.id, charge.merchant.webhook_secret)

    # Fire the merchant webhook in the background.
    delivery = enqueue_charge_event(db, charge, charge.merchant, "charge.paid")
    if delivery:
        background.add_task(deliver_webhook, delivery.id, charge.merchant.webhook_secret)

    return get_checkout(charge_id, db)
