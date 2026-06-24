"""Runtime, DB-backed platform settings (toggled by admins).

Distinct from config.Settings (env-based, read at startup). These can change at
runtime via the admin console.
"""

from sqlalchemy.orm import Session

from .models import Setting

# Setting keys
AUTO_BANK_CHECK = "auto_bank_check"  # enable /bank/incoming auto-settlement


def get_bool(db: Session, key: str, default: bool = False) -> bool:
    row = db.get(Setting, key)
    if row is None:
        return default
    return str(row.value).lower() in ("1", "true", "yes", "on")


def set_bool(db: Session, key: str, value: bool) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value="true" if value else "false"))
    else:
        row.value = "true" if value else "false"
    db.commit()
