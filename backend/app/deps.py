from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdminUser, ApiKey, Merchant, utcnow
from .security import decode_access_token, decode_admin_token, hash_api_key


def get_current_merchant(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Merchant:
    """Dashboard auth via JWT bearer token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    merchant_id = decode_access_token(token)
    if not merchant_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    merchant = db.get(Merchant, merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Merchant not found")
    if merchant.suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Merchant account suspended")
    return merchant


def get_current_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Platform admin auth via JWT bearer token (typ=admin)."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    admin_id = decode_admin_token(token)
    if not admin_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    admin = db.get(AdminUser, admin_id)
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin not found")
    return admin


def get_api_merchant(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Merchant:
    """API auth via secret key (Authorization: Bearer sk_... or X-API-Key)."""
    key = None
    if x_api_key:
        key = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        candidate = authorization.split(" ", 1)[1].strip()
        if candidate.startswith("sk_"):
            key = candidate
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing API key")

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.secret_hash == hash_api_key(key), ApiKey.revoked.is_(False))
        .first()
    )
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    api_key.last_used_at = utcnow()
    db.commit()
    merchant = db.get(Merchant, api_key.merchant_id)
    if not merchant:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Merchant not found")
    if merchant.suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Merchant account suspended")
    return merchant
