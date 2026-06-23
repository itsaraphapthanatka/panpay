"""Member notifications (email + SMS) for bills and payments.

Pluggable like slip verification: real email goes via SMTP and SMS via a generic
HTTP gateway when configured; otherwise messages are recorded to NotificationLog
(console provider) so the flow is fully testable without external credentials.
Every send — sent, failed, or skipped — is recorded for auditing.
"""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .models import NotificationLog


def _baht(n) -> str:
    return "฿" + f"{float(n):,.2f}"


def _checkout_url(charge) -> str:
    return f"{settings.checkout_base_url}/pay/{charge.id}"


def _portal_url(subscription) -> str | None:
    if subscription.portal_token:
        return f"{settings.checkout_base_url}/m/{subscription.portal_token}"
    return None


def _record(db: Session, *, merchant_id, subscription_id, channel, recipient, event,
            subject, body, status, provider, error=None) -> NotificationLog:
    log = NotificationLog(
        merchant_id=merchant_id, subscription_id=subscription_id, channel=channel,
        recipient=recipient, event=event, subject=subject, body=body, status=status,
        provider=provider, error=error,
    )
    db.add(log)
    db.commit()
    return log


# ---- channel senders ----
def _send_email(to: str, subject: str, body: str) -> tuple[str, str, str | None]:
    """Returns (status, provider, error)."""
    if not settings.smtp_host:
        return "skipped", "console", None  # no SMTP configured -> just log
    try:
        msg = EmailMessage()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_tls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return "sent", "smtp", None
    except Exception as exc:  # noqa: BLE001
        return "failed", "smtp", str(exc)


def _send_sms(to: str, body: str) -> tuple[str, str, str | None]:
    if not settings.sms_api_url:
        return "skipped", "console", None
    try:
        resp = httpx.post(
            settings.sms_api_url,
            headers={"Authorization": f"Bearer {settings.sms_api_key}"} if settings.sms_api_key else {},
            json={"to": to, "message": body},
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            return "sent", "http", None
        return "failed", "http", f"status_{resp.status_code}"
    except httpx.HTTPError as exc:
        return "failed", "http", str(exc)


def _send_line(to_user_id: str, body: str) -> tuple[str, str, str | None]:
    """Push a text message to a member via the LINE Messaging API."""
    if not settings.line_channel_access_token:
        return "skipped", "console", None
    try:
        resp = httpx.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {settings.line_channel_access_token}"},
            json={"to": to_user_id, "messages": [{"type": "text", "text": body}]},
            timeout=15,
        )
        if 200 <= resp.status_code < 300:
            return "sent", "line", None
        detail = ""
        try:
            detail = resp.json().get("message", "")
        except Exception:  # noqa: BLE001
            pass
        return "failed", "line", f"status_{resp.status_code} {detail}".strip()
    except httpx.HTTPError as exc:
        return "failed", "line", str(exc)


def _notify(db: Session, subscription, event: str, subject: str, email_body: str, sms_body: str) -> None:
    merchant_id = subscription.merchant_id
    sub_id = subscription.id
    if subscription.customer_email:
        status, provider, error = _send_email(subscription.customer_email, subject, email_body)
        _record(db, merchant_id=merchant_id, subscription_id=sub_id, channel="email",
                recipient=subscription.customer_email, event=event, subject=subject,
                body=email_body, status=status, provider=provider, error=error)
    if subscription.customer_phone:
        status, provider, error = _send_sms(subscription.customer_phone, sms_body)
        _record(db, merchant_id=merchant_id, subscription_id=sub_id, channel="sms",
                recipient=subscription.customer_phone, event=event, subject=None,
                body=sms_body, status=status, provider=provider, error=error)
    if subscription.customer_line_id:
        status, provider, error = _send_line(subscription.customer_line_id, sms_body)
        _record(db, merchant_id=merchant_id, subscription_id=sub_id, channel="line",
                recipient=subscription.customer_line_id, event=event, subject=None,
                body=sms_body, status=status, provider=provider, error=error)


# ---- public events ----
def notify_invoice_issued(db: Session, subscription, charge, business_name: str) -> None:
    pay = _portal_url(subscription) or _checkout_url(charge)
    subject = f"[{business_name}] บิลค่าสมาชิก {_baht(charge.amount)}"
    email_body = (
        f"เรียน {subscription.customer_name},\n\n"
        f"มีบิลค่าสมาชิกจำนวน {_baht(charge.amount)} รอการชำระเงิน\n"
        f"ชำระเงินได้ที่: {pay}\n\n— {business_name}"
    )
    sms_body = f"{business_name}: บิลค่าสมาชิก {_baht(charge.amount)} ชำระที่ {pay}"
    _notify(db, subscription, "invoice.issued", subject, email_body, sms_body)


def notify_payment_received(db: Session, subscription, charge, business_name: str) -> None:
    subject = f"[{business_name}] รับชำระเงิน {_baht(charge.amount)} แล้ว"
    until = subscription.current_period_end
    until_txt = f"\nสมาชิกใช้งานได้ถึง {until.strftime('%d/%m/%Y')}" if until else ""
    email_body = (
        f"เรียน {subscription.customer_name},\n\n"
        f"ได้รับชำระเงิน {_baht(charge.amount)} เรียบร้อยแล้ว{until_txt}\n\n— {business_name}"
    )
    sms_body = f"{business_name}: รับชำระ {_baht(charge.amount)} แล้ว ขอบคุณค่ะ"
    _notify(db, subscription, "payment.received", subject, email_body, sms_body)
