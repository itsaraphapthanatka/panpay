import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta

import jwt

from .config import settings
from .models import utcnow

# ---- Passwords (stdlib PBKDF2-HMAC-SHA256, no native deps) ----
_PBKDF2_ROUNDS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(_PBKDF2_ROUNDS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(dk).decode("ascii"),
        ]
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, rounds, salt_b64, hash_b64 = password_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


# ---- Dashboard JWT sessions ----
def create_access_token(merchant_id: str) -> str:
    now = utcnow()
    payload = {
        "sub": merchant_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # Admin tokens must never authenticate a merchant session.
        if payload.get("typ") == "admin":
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# ---- Admin JWT sessions ----
def create_admin_token(admin_id: str) -> str:
    now = utcnow()
    payload = {
        "sub": admin_id,
        "typ": "admin",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_admin_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != "admin":
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


# ---- API keys ----
def generate_api_key(mode: str = "live") -> tuple[str, str, str, str]:
    """Returns (full_key, secret_hash, prefix, last_four)."""
    raw = secrets.token_hex(24)
    full = f"sk_{mode}_{raw}"
    secret_hash = hashlib.sha256(full.encode("utf-8")).hexdigest()
    prefix = full[:12]
    last_four = full[-4:]
    return full, secret_hash, prefix, last_four


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


# ---- Webhook signatures ----
def sign_webhook(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
