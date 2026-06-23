from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://panpay:panpay@localhost:5432/panpay"

    jwt_secret: str = "dev-only-insecure-secret-change-me-in-production-0123456789"
    jwt_expire_minutes: int = 720
    jwt_algorithm: str = "HS256"

    # Platform admin bootstrap: if both are set, the first admin is created on
    # startup when no admin exists yet. Leave blank in favour of create_admin.py.
    admin_bootstrap_email: str = ""
    admin_bootstrap_password: str = ""

    checkout_base_url: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"

    # Slip verification
    slip_provider: str = "dev"  # "dev" | "slipok" | "easyslip"
    slipok_api_key: str = ""
    slipok_branch_id: str = ""
    easyslip_api_key: str = ""
    dev_auto_verify: bool = True

    # Subscription renewals
    subscription_grace_days: int = 3  # days past period end before a member expires
    run_scheduler: bool = False  # in-process daily renewal job (single-instance only)
    scheduler_interval_hours: int = 24

    # Notifications (email via SMTP, SMS via a generic HTTP gateway). Unset = console/log only.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "PanPay <no-reply@panpay.local>"
    smtp_tls: bool = True
    sms_api_url: str = ""
    sms_api_key: str = ""
    # LINE Messaging API (free push within quota). Channel access token from the LINE console.
    line_channel_access_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
