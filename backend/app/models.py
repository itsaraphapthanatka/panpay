import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Setting(Base):
    """Platform-wide key/value settings, toggled at runtime by an admin."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AdminUser(Base):
    """Platform operator who oversees every merchant on the gateway."""

    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "adm_" + _uuid())
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, default="Admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "mch_" + _uuid())
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    business_name: Mapped[str] = mapped_column(String)
    # Suspended merchants are blocked from authenticating (dashboard + API).
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # PromptPay proxy that receives the money (phone / national id / e-wallet id)
    promptpay_id: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_secret: Mapped[str] = mapped_column(String, default=lambda: "whsec_" + _uuid())
    # Service fee applied when settling collected payments.
    fee_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    fee_fixed: Mapped[float] = mapped_column(Numeric(8, 2), default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="merchant", cascade="all, delete-orphan")
    charges: Mapped[list["Charge"]] = relationship(back_populates="merchant", cascade="all, delete-orphan")
    receiving_accounts: Mapped[list["ReceivingAccount"]] = relationship(
        back_populates="merchant", cascade="all, delete-orphan"
    )


class ReceivingAccount(Base):
    """A PromptPay destination the merchant can receive into (e.g. per branch/account)."""

    __tablename__ = "receiving_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "rcv_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    promptpay_id: Mapped[str] = mapped_column(String)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    merchant: Mapped[Merchant] = relationship(back_populates="receiving_accounts")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "key_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String, default="Secret key")
    # sha256 of the full secret; used to look up the key on each request
    secret_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String)  # e.g. "sk_live_a1b2"
    last_four: Mapped[str] = mapped_column(String)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    merchant: Mapped[Merchant] = relationship(back_populates="api_keys")


class Charge(Base):
    __tablename__ = "charges"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "chg_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="THB")
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)  # merchant's order id
    # pending | paid | expired | canceled | refunded
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    receiving_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("receiving_accounts.id"), nullable=True
    )
    settlement_id: Mapped[str | None] = mapped_column(ForeignKey("settlements.id"), nullable=True, index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"), nullable=True, index=True)
    promptpay_payload: Mapped[str] = mapped_column(Text)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    merchant: Mapped[Merchant] = relationship(back_populates="charges")
    payment: Mapped["Payment | None"] = relationship(back_populates="charge", uselist=False)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "pay_" + _uuid())
    charge_id: Mapped[str] = mapped_column(ForeignKey("charges.id"), index=True)
    # Bank transaction reference from the slip — globally unique so a slip can't be reused.
    trans_ref: Mapped[str] = mapped_column(String, unique=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    sender_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sender_bank: Mapped[str | None] = mapped_column(String, nullable=True)
    receiver_name: Mapped[str | None] = mapped_column(String, nullable=True)
    receiver_bank: Mapped[str | None] = mapped_column(String, nullable=True)
    # When the transfer actually happened, as reported by the slip / provider.
    transferred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str] = mapped_column(String)  # dev | slipok | easyslip
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    charge: Mapped[Charge] = relationship(back_populates="payment")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "whd_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    charge_id: Mapped[str] = mapped_column(String, index=True)
    event: Mapped[str] = mapped_column(String)  # charge.paid
    url: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|success|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    """A membership package a merchant offers (recurring billing interval)."""

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "pln_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="THB")
    interval_unit: Mapped[str] = mapped_column(String, default="month")  # day | month | year
    interval_count: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    """A member's subscription to a plan."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "sub_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), index=True)
    customer_name: Mapped[str] = mapped_column(String)
    customer_email: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_line_id: Mapped[str | None] = mapped_column(String, nullable=True)  # LINE userId (Uxxxx)
    customer_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    coupon_id: Mapped[str | None] = mapped_column(ForeignKey("coupons.id"), nullable=True)
    # pending (awaiting first payment) | active | past_due (renewal due) | expired | canceled
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when the membership ends (canceled or expired) — used for churn metrics.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Unguessable token for the public self-service portal (/m/{token}).
    portal_token: Mapped[str | None] = mapped_column(
        String, unique=True, nullable=True, default=lambda: "mpt_" + _uuid()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    plan: Mapped[Plan] = relationship()


class Coupon(Base):
    """A discount a merchant can apply to a member's subscription invoices."""

    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("merchant_id", "code", name="uq_coupon_merchant_code"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "cpn_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    code: Mapped[str] = mapped_column(String, index=True)
    discount_type: Mapped[str] = mapped_column(String)  # percent | fixed
    value: Mapped[float] = mapped_column(Numeric(12, 2))
    duration: Mapped[str] = mapped_column(String, default="once")  # once | forever
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    max_redemptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    times_redeemed: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationLog(Base):
    """Record of bill/payment notifications sent to members (or skipped)."""

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "ntf_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(String, index=True)
    subscription_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    channel: Mapped[str] = mapped_column(String)  # email | sms
    recipient: Mapped[str | None] = mapped_column(String, nullable=True)
    event: Mapped[str] = mapped_column(String)  # invoice.issued | payment.received
    subject: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)  # sent | failed | skipped
    provider: Mapped[str] = mapped_column(String)  # console | smtp | http
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Settlement(Base):
    """A batch of collected payments reconciled into a payout to the merchant."""

    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "stl_" + _uuid())
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    fee_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    charge_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending", index=True)  # pending | paid_out
    reference: Mapped[str | None] = mapped_column(String, nullable=True)  # payout reference
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    paid_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Append-only record of security/finance-relevant actions."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: "log_" + _uuid())
    merchant_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    actor: Mapped[str] = mapped_column(String)  # email, "api", or "anonymous"
    action: Mapped[str] = mapped_column(String, index=True)  # e.g. charge.create, auth.login
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
