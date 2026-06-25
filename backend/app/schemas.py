from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    business_name: str
    promptpay_id: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MerchantOut(BaseModel):
    id: str
    email: str
    business_name: str
    promptpay_id: str | None
    webhook_url: str | None
    webhook_secret: str
    fee_percent: float
    fee_fixed: float
    created_at: datetime

    class Config:
        from_attributes = True


class MerchantSettingsUpdate(BaseModel):
    business_name: str | None = None
    promptpay_id: str | None = None
    webhook_url: str | None = None
    fee_percent: float | None = Field(default=None, ge=0, le=100)
    fee_fixed: float | None = Field(default=None, ge=0)


# ---- API keys ----
class ApiKeyCreate(BaseModel):
    name: str = "Secret key"


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    last_four: str
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class ApiKeyCreated(ApiKeyOut):
    secret: str  # full key, shown only once


# ---- Charges ----
class ChargeCreate(BaseModel):
    amount: float = Field(gt=0)
    description: str | None = None
    reference: str | None = None
    metadata: dict = Field(default_factory=dict)
    expires_in: int | None = Field(default=None, description="seconds until the QR expires")
    account_id: str | None = Field(default=None, description="receiving account to credit")


class RefundRequest(BaseModel):
    reason: str | None = None


class PaymentOut(BaseModel):
    trans_ref: str
    amount: float
    sender_name: str | None
    sender_bank: str | None
    receiver_name: str | None
    receiver_bank: str | None
    transferred_at: datetime | None
    provider: str

    class Config:
        from_attributes = True


class ChargeOut(BaseModel):
    id: str
    amount: float
    currency: str
    status: str
    description: str | None
    reference: str | None
    metadata: dict
    checkout_url: str
    expires_at: datetime | None
    paid_at: datetime | None
    canceled_at: datetime | None = None
    refunded_at: datetime | None = None
    refund_reason: str | None = None
    created_at: datetime
    payment: PaymentOut | None = None


class ChargePublic(BaseModel):
    """What the public checkout page may see — no internal merchant data."""

    id: str
    amount: float
    currency: str
    status: str
    description: str | None
    business_name: str
    qr_image: str  # data URI
    qr_payload: str
    expires_at: datetime | None
    paid_at: datetime | None = None
    payment: PaymentOut | None = None


class SlipSubmitJSON(BaseModel):
    qr_payload: str | None = None
    trans_ref: str | None = None


# ---- Top-up / merchant wallet ----
class TopupCreate(BaseModel):
    amount: float = Field(gt=0, description="amount of credit to add")


class TopupOut(BaseModel):
    id: str
    amount: float
    pay_amount: float          # exact amount to transfer (unique satang)
    status: str
    method: str | None = None
    qr_image: str = ""         # data URI
    qr_payload: str = ""
    sender_name: str | None = None
    expires_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class WalletEntryOut(BaseModel):
    id: str
    amount: float
    type: str
    balance_after: float
    description: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class BalanceOut(BaseModel):
    balance: float
    credit_per_transaction: float   # effective rate for this merchant
    entries: list[WalletEntryOut]


class TopupIncomingRequest(BaseModel):
    amount: float = Field(gt=0)
    ref: str | None = None
    sender_name: str | None = None


class TopupIncomingResult(BaseModel):
    matched: bool
    topup_id: str | None = None
    merchant_id: str | None = None
    amount: float | None = None
    reason: str | None = None


# ---- Bank notification ingest (auto-match incoming transfers, no slip) ----
class BankIncomingRequest(BaseModel):
    amount: float = Field(gt=0, description="amount credited, as read from the bank notification")
    ref: str | None = Field(default=None, description="bank transaction ref if available (dedupe)")
    sender_name: str | None = None
    transferred_at: datetime | None = None
    raw: dict = Field(default_factory=dict, description="raw notification text/payload for the record")


class BankIncomingResult(BaseModel):
    matched: bool
    charge_id: str | None = None
    amount: float | None = None
    reason: str | None = None  # why no match, when matched is false
    candidates: int = 0        # how many pending charges had this amount


# ---- Receiving accounts ----
class ReceivingAccountCreate(BaseModel):
    name: str
    promptpay_id: str
    is_default: bool = False


class ReceivingAccountOut(BaseModel):
    id: str
    name: str
    promptpay_id: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Audit log ----
class AuditLogOut(BaseModel):
    id: str
    actor: str
    action: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    extra: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Settlements ----
class SettlementGenerate(BaseModel):
    period_start: datetime | None = None
    period_end: datetime | None = None


class PayoutRequest(BaseModel):
    reference: str | None = None


class SettlementOut(BaseModel):
    id: str
    period_start: datetime | None
    period_end: datetime | None
    gross_amount: float
    fee_amount: float
    net_amount: float
    charge_count: int
    status: str
    reference: str | None
    created_at: datetime
    paid_out_at: datetime | None

    class Config:
        from_attributes = True


# ---- Membership: plans ----
class PlanCreate(BaseModel):
    name: str
    amount: float = Field(gt=0)
    interval_unit: str = Field(default="month", pattern="^(day|month|year)$")
    interval_count: int = Field(default=1, ge=1)
    description: str | None = None


class PlanUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    description: str | None = None


class PlanOut(BaseModel):
    id: str
    name: str
    amount: float
    currency: str
    interval_unit: str
    interval_count: int
    description: str | None
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Membership: subscriptions ----
class SubscriptionCreate(BaseModel):
    plan_id: str
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    customer_line_id: str | None = None
    customer_ref: str | None = None
    coupon_code: str | None = None


class ChangePlanRequest(BaseModel):
    plan_id: str


# ---- Coupons ----
class CouponCreate(BaseModel):
    code: str = Field(min_length=1)
    discount_type: str = Field(pattern="^(percent|fixed)$")
    value: float = Field(gt=0)
    duration: str = Field(default="once", pattern="^(once|forever)$")
    max_redemptions: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None


class CouponOut(BaseModel):
    id: str
    code: str
    discount_type: str
    value: float
    duration: str
    active: bool
    max_redemptions: int | None
    times_redeemed: int
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationLogOut(BaseModel):
    id: str
    subscription_id: str | None
    channel: str
    recipient: str | None
    event: str
    status: str
    provider: str
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionOut(BaseModel):
    id: str
    plan_id: str
    plan_name: str | None = None
    customer_name: str
    customer_email: str | None
    customer_phone: str | None = None
    customer_line_id: str | None = None
    customer_ref: str | None
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    canceled_at: datetime | None
    ended_at: datetime | None = None
    portal_url: str | None = None
    created_at: datetime


class SubscriptionStats(BaseModel):
    active_members: int
    mrr: float
    arr: float
    new_this_month: int
    churned_this_month: int
    churn_rate: float
    by_status: dict


# ---- Customer portal (public, token-auth) ----
class PortalView(BaseModel):
    business_name: str
    customer_name: str
    plan_name: str | None
    plan_amount: float | None
    interval_unit: str | None
    interval_count: int | None
    status: str
    current_period_end: datetime | None
    open_invoice_url: str | None
    invoices: list[ChargeOut]


class PortalRenewResult(BaseModel):
    checkout_url: str


class SubscriptionCreated(BaseModel):
    subscription: SubscriptionOut
    invoice: ChargeOut


class SubscriptionDetail(BaseModel):
    subscription: SubscriptionOut
    invoices: list[ChargeOut]


# ---- Admin (platform operator) ----
class AdminOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class AdminMerchantOut(BaseModel):
    """A merchant row in the admin console, enriched with rollup stats."""

    id: str
    email: str
    business_name: str
    promptpay_id: str | None
    suspended: bool
    fee_percent: float
    fee_fixed: float
    balance: float = 0
    credit_per_transaction: float | None = None  # null = uses global rate
    created_at: datetime
    charge_count: int = 0
    paid_count: int = 0
    paid_amount: float = 0
    pending_count: int = 0


class AdminMerchantUpdate(BaseModel):
    fee_percent: float | None = Field(default=None, ge=0, le=100)
    fee_fixed: float | None = Field(default=None, ge=0)
    suspended: bool | None = None
    # Per-merchant credit rate override. Send null to clear (use global rate).
    credit_per_transaction: float | None = Field(default=None, ge=0)
    clear_credit_override: bool = False  # set true to reset to the global rate


class AdminChargeOut(ChargeOut):
    merchant_id: str
    business_name: str


class AdminSettlementOut(SettlementOut):
    merchant_id: str
    business_name: str


class AdminSettingsOut(BaseModel):
    auto_bank_check: bool
    platform_promptpay: str
    topup_ingest_key: str
    credit_per_transaction: float


class AdminSettingsUpdate(BaseModel):
    auto_bank_check: bool | None = None
    platform_promptpay: str | None = None
    credit_per_transaction: float | None = Field(default=None, ge=0)
    regenerate_ingest_key: bool = False


class AdminStats(BaseModel):
    merchant_count: int
    suspended_count: int
    total_paid_amount: float
    paid_count: int
    pending_count: int
    today_amount: float
    today_count: int
    total_fee_amount: float  # net fees collected across paid-out settlements


# ---- Dashboard ----
class DashboardStats(BaseModel):
    total_paid_amount: float
    paid_count: int
    pending_count: int
    today_amount: float
    today_count: int
    series: list[dict]  # [{date, amount, count}]
