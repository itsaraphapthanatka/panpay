"""Create a demo merchant + API key so you can try the gateway immediately.

Runs pending Alembic migrations first, then seeds.
Run:  python seed.py
"""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.database import SessionLocal
from app.models import ApiKey, Merchant
from app.security import generate_api_key, hash_password

DEMO_EMAIL = "demo@panpay.io"
DEMO_PASSWORD = "demo1234"


def run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    command.upgrade(cfg, "head")


def main() -> None:
    run_migrations()
    db = SessionLocal()
    try:
        merchant = db.query(Merchant).filter(Merchant.email == DEMO_EMAIL).first()
        if merchant:
            print(f"Demo merchant already exists: {DEMO_EMAIL}")
        else:
            merchant = Merchant(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                business_name="PanPay Demo Shop",
                promptpay_id="0812345678",  # demo PromptPay phone proxy
            )
            db.add(merchant)
            db.commit()
            db.refresh(merchant)
            print(f"Created demo merchant: {DEMO_EMAIL} / {DEMO_PASSWORD}")

        full, secret_hash, prefix, last_four = generate_api_key()
        key = ApiKey(
            merchant_id=merchant.id,
            name="Seed key",
            secret_hash=secret_hash,
            prefix=prefix,
            last_four=last_four,
        )
        db.add(key)
        db.commit()
        print("\n=== Demo credentials ===")
        print(f"Dashboard login : {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"API secret key  : {full}")
        print("(store this key now — it is not shown again)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
