"""Runtime, DB-backed platform settings (toggled by admins).

Distinct from config.Settings (env-based, read at startup). These can change at
runtime via the admin console.
"""

import secrets

from sqlalchemy.orm import Session

from .models import Setting

# Setting keys
AUTO_BANK_CHECK = "auto_bank_check"        # enable /bank/incoming auto-settlement
PLATFORM_PROMPTPAY = "platform_promptpay"  # PromptPay id that receives merchant top-ups
PLATFORM_RECEIVER_NAME = "platform_receiver_name"      # account holder name (TH) for slip checkReceiver
PLATFORM_RECEIVER_ACCOUNT = "platform_receiver_account"  # account number (masked ok) for checkReceiver
TOPUP_INGEST_KEY = "topup_ingest_key"      # secret for the platform top-up forwarder
CREDIT_PER_TRANSACTION = "credit_per_transaction"  # global credit charged per processed txn
DEFAULT_CREDIT_PER_TRANSACTION = "0.5"
TOPUP_UNIQUE_SATANG = "topup_unique_satang"  # add a unique satang suffix to top-up amounts


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    row = db.get(Setting, key)
    if row is None:
        return default
    return str(row.value).lower() in ("1", "true", "yes", "on")


def set_bool(db: Session, key: str, value: bool) -> None:
    set_str(db, key, "true" if value else "false")


def get_str(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row is not None else default


def set_str(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def ensure_ingest_key(db: Session) -> str:
    """Return the platform top-up ingest key, creating one if not set yet."""
    key = get_str(db, TOPUP_INGEST_KEY)
    if not key:
        key = "tik_" + secrets.token_hex(20)
        set_str(db, TOPUP_INGEST_KEY, key)
    return key
