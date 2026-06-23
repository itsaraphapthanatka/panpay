from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..deps import get_current_merchant
from ..models import Merchant
from ..ratelimit import limit_auth
from ..schemas import (
    LoginRequest,
    MerchantOut,
    RegisterRequest,
    TokenResponse,
)
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(limit_auth)])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    existing = db.query(Merchant).filter(Merchant.email == body.email).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    merchant = Merchant(
        email=body.email,
        password_hash=hash_password(body.password),
        business_name=body.business_name,
        promptpay_id=body.promptpay_id,
    )
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    audit.record(db, action="auth.register", actor=merchant.email, merchant_id=merchant.id,
                 request=request)
    return TokenResponse(access_token=create_access_token(merchant.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    merchant = db.query(Merchant).filter(Merchant.email == body.email).first()
    if not merchant or not verify_password(body.password, merchant.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    audit.record(db, action="auth.login", actor=merchant.email, merchant_id=merchant.id,
                 request=request)
    return TokenResponse(access_token=create_access_token(merchant.id))


@router.get("/me", response_model=MerchantOut)
def me(merchant: Merchant = Depends(get_current_merchant)):
    return merchant
