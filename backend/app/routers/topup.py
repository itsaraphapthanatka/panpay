"""Merchant prepaid top-up: dashboard endpoints + platform bank-ingest.

- /dashboard/topups*   — merchant creates/lists top-ups, checks balance, uploads slip
- /topup/incoming      — platform forwarder posts incoming transfers (X-Ingest-Key),
                         matched to a pending top-up by its unique amount
"""

import secrets

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..deps import get_current_merchant
from ..models import Merchant, Topup, WalletEntry, utcnow
from ..promptpay import payload_to_data_uri
from ..schemas import (
    BalanceOut,
    TopupCreate,
    TopupIncomingRequest,
    TopupIncomingResult,
    TopupOut,
    WalletEntryOut,
)
from ..billing import credit_rate
from ..slip_qr import decode_qr
from ..slip_verify import get_verifier
from ..settings_store import (
    PLATFORM_RECEIVER_ACCOUNT,
    PLATFORM_RECEIVER_NAME,
    ensure_ingest_key,
    get_str,
)
from ..topup_ops import (
    AMOUNT_TOLERANCE,
    cancel_topup,
    complete_topup,
    create_topup,
    expire_if_needed,
    pending_by_amount,
)

router = APIRouter(tags=["topup"])


def _to_out(topup: Topup, *, with_qr: bool = True) -> TopupOut:
    return TopupOut(
        id=topup.id,
        amount=float(topup.amount),
        pay_amount=float(topup.pay_amount),
        status=topup.status,
        method=topup.method,
        qr_image=payload_to_data_uri(topup.promptpay_payload) if with_qr else "",
        qr_payload=topup.promptpay_payload if with_qr else "",
        sender_name=topup.sender_name,
        expires_at=topup.expires_at,
        completed_at=topup.completed_at,
        created_at=topup.created_at,
    )


def _owned(db: Session, topup_id: str, merchant: Merchant) -> Topup:
    topup = db.get(Topup, topup_id)
    if not topup or topup.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Top-up not found")
    return topup


# ---- Merchant dashboard ----
@router.post("/dashboard/topups", response_model=TopupOut, status_code=status.HTTP_201_CREATED)
def create(
    body: TopupCreate,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    topup = create_topup(db, merchant, body.amount)
    audit.record(db, action="topup.create", actor=merchant.email, merchant_id=merchant.id,
                 target_type="topup", target_id=topup.id, request=request,
                 extra={"amount": float(topup.amount), "pay_amount": float(topup.pay_amount)})
    return _to_out(topup)


@router.get("/dashboard/topups", response_model=list[TopupOut])
def list_topups(merchant: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)):
    rows = (
        db.query(Topup).filter(Topup.merchant_id == merchant.id)
        .order_by(Topup.created_at.desc()).limit(100).all()
    )
    return [_to_out(t, with_qr=False) for t in rows]


@router.get("/dashboard/topups/{topup_id}", response_model=TopupOut)
def get_topup(topup_id: str, merchant: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)):
    topup = _owned(db, topup_id, merchant)
    expire_if_needed(db, topup)
    return _to_out(topup)


@router.post("/dashboard/topups/{topup_id}/slip", response_model=TopupOut)
def submit_slip(
    topup_id: str,
    request: Request,
    file: UploadFile | None = File(default=None),
    qr_payload: str | None = Form(default=None),
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    topup = _owned(db, topup_id, merchant)
    expire_if_needed(db, topup)
    if topup.status == "completed":
        return _to_out(topup)
    if topup.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Top-up is {topup.status}")

    file_bytes = file.file.read() if file else None
    if file_bytes and not qr_payload:
        qr_payload = decode_qr(file_bytes)

    # Verify the slip's receiver is the platform account (anti-fraud): otherwise a
    # merchant could credit themselves with any genuine slip of the right amount.
    # Send name and account as SEPARATE conditions — Slip2Go treats the array as
    # OR ("ตรงอย่างน้อย 1 เงื่อนไข"). PromptPay-to-phone slips show only the proxy
    # (phone), not the bank account number, so the name usually is what matches.
    recv_name = get_str(db, PLATFORM_RECEIVER_NAME)
    recv_acct = get_str(db, PLATFORM_RECEIVER_ACCOUNT)
    check_receiver = []
    if recv_name:
        check_receiver.append({"accountNameTH": recv_name})
    if recv_acct:
        check_receiver.append({"accountNumber": recv_acct})
    check_receiver = check_receiver or None

    result = get_verifier().verify(
        expected_amount=float(topup.pay_amount),
        file_bytes=file_bytes, qr_payload=qr_payload, trans_ref=None,
        check_receiver=check_receiver,
    )
    if not result.success:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"ตรวจสลิปไม่ผ่าน: {result.error or 'unknown'}")
    if result.amount is None or abs(float(result.amount) - float(topup.pay_amount)) > AMOUNT_TOLERANCE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"ยอดในสลิป ({result.amount}) ไม่ตรงกับยอดที่ต้องโอน ({float(topup.pay_amount)})")

    topup = complete_topup(db, topup, method="slip",
                           trans_ref=result.trans_ref or ("SLIP" + secrets.token_hex(8).upper()),
                           sender_name=result.sender_name)
    audit.record(db, action="topup.paid", actor=merchant.email, merchant_id=merchant.id,
                 target_type="topup", target_id=topup.id, request=request, extra={"method": "slip"})
    return _to_out(topup)


@router.post("/dashboard/topups/{topup_id}/cancel", response_model=TopupOut)
def cancel(
    topup_id: str,
    request: Request,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    topup = _owned(db, topup_id, merchant)
    expire_if_needed(db, topup)
    topup = cancel_topup(db, topup)
    audit.record(db, action="topup.cancel", actor=merchant.email, merchant_id=merchant.id,
                 target_type="topup", target_id=topup.id, request=request)
    return _to_out(topup, with_qr=False)


@router.get("/dashboard/balance", response_model=BalanceOut)
def balance(merchant: Merchant = Depends(get_current_merchant), db: Session = Depends(get_db)):
    entries = (
        db.query(WalletEntry).filter(WalletEntry.merchant_id == merchant.id)
        .order_by(WalletEntry.created_at.desc()).limit(50).all()
    )
    return BalanceOut(
        balance=float(merchant.balance or 0),
        credit_per_transaction=credit_rate(db, merchant),
        entries=[WalletEntryOut.model_validate(e) for e in entries],
    )


# ---- Platform top-up ingest (the platform's bank forwarder) ----
@router.post("/topup/incoming", response_model=TopupIncomingResult)
def topup_incoming(
    body: TopupIncomingRequest,
    request: Request,
    x_ingest_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = ensure_ingest_key(db)
    if not x_ingest_key or not secrets.compare_digest(x_ingest_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid ingest key")

    candidates = pending_by_amount(db, body.amount)
    if not candidates:
        audit.record(db, action="topup.incoming.unmatched", actor="bank",
                     request=request, extra={"amount": body.amount, "ref": body.ref})
        return TopupIncomingResult(matched=False, amount=body.amount,
                                   reason="no_pending_topup_for_amount")
    if len(candidates) > 1:
        # Sender-account disambiguation is disabled for now (payers may transfer
        # from a different account). Same-amount collisions fall back to slip.
        audit.record(db, action="topup.incoming.ambiguous", actor="bank", request=request,
                     extra={"amount": body.amount, "ref": body.ref, "candidates": len(candidates)})
        return TopupIncomingResult(matched=False, amount=body.amount, reason="ambiguous_amount")
    topup = candidates[0]

    trans_ref = body.ref or ("BANK" + secrets.token_hex(10).upper())
    topup = complete_topup(db, topup, method="bank_auto", trans_ref=trans_ref,
                           sender_name=body.sender_name)
    audit.record(db, action="topup.paid", actor="bank", merchant_id=topup.merchant_id,
                 target_type="topup", target_id=topup.id, request=request, extra={"method": "bank_auto"})
    return TopupIncomingResult(matched=True, topup_id=topup.id, merchant_id=topup.merchant_id,
                               amount=float(topup.pay_amount))
