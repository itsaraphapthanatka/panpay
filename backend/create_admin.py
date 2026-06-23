"""Create (or update the password of) a platform admin.

Runs pending Alembic migrations first, then upserts the admin.

Usage:
    python create_admin.py <email> <password> [name]
    python create_admin.py                      # prompts interactively
"""

import getpass
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.database import SessionLocal
from app.models import AdminUser
from app.security import hash_password


def run_migrations() -> None:
    cfg = Config(str(Path(__file__).resolve().parent / "alembic.ini"))
    command.upgrade(cfg, "head")


def main() -> None:
    args = sys.argv[1:]
    email = args[0] if len(args) > 0 else input("Admin email: ").strip()
    password = args[1] if len(args) > 1 else getpass.getpass("Admin password: ")
    name = args[2] if len(args) > 2 else "Admin"

    if not email or not password:
        sys.exit("email and password are required")

    run_migrations()
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.email == email).first()
        if admin:
            admin.password_hash = hash_password(password)
            admin.name = name
            db.commit()
            print(f"Updated admin password: {email}")
        else:
            db.add(AdminUser(email=email, password_hash=hash_password(password), name=name))
            db.commit()
            print(f"Created admin: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
