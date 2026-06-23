"""Append-only audit logging helper."""

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog
from .ratelimit import client_ip


def record(
    db: Session,
    *,
    action: str,
    actor: str = "anonymous",
    merchant_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    request: Request | None = None,
    extra: dict | None = None,
) -> None:
    log = AuditLog(
        merchant_id=merchant_id,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip=client_ip(request),
        extra=extra or {},
    )
    db.add(log)
    db.commit()
