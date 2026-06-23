"""Pytest fixtures for the PanPay backend.

Tests run against a dedicated Postgres database (default: panpay_test) so they
never touch dev/demo data. The DB is created if missing (the role needs
CREATEDB), the schema is built once per session, and every test starts from a
clean slate (tables truncated + rate limiter reset).
"""

import os

# Configure the app for tests BEFORE importing any app module (engine binds at import).
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://panpay:panpay@localhost:5432/panpay_test")
os.environ.setdefault("SLIP_PROVIDER", "dev")
os.environ.setdefault("DEV_AUTO_VERIFY", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key-of-sufficient-length-0123456789")
os.environ.setdefault("CHECKOUT_BASE_URL", "http://testserver")

import secrets  # noqa: E402

import psycopg  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _ensure_database() -> None:
    """Create the test database if it does not exist yet."""
    url = os.environ["DATABASE_URL"].split("://", 1)[1]
    creds, hostpart = url.split("@", 1)
    user, password = creds.split(":", 1)
    hostport, dbname = hostpart.split("/", 1)
    host, _, port = hostport.partition(":")
    try:
        conn = psycopg.connect(
            host=host, port=port or "5432", user=user, password=password,
            dbname="postgres", autocommit=True,
        )
    except Exception:
        return  # assume the DB was provisioned externally
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        conn.close()


_ensure_database()

from app import models  # noqa: E402,F401  (register tables)
from app import ratelimit  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean():
    """Reset state before each test: truncate all tables + clear rate limiter."""
    ratelimit._store.clear()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def merchant(client):
    """A registered merchant with a PromptPay id; returns auth headers + email."""
    email = f"m_{secrets.token_hex(4)}@panpay.io"
    r = client.post("/auth/register", json={
        "email": email, "password": "secret123",
        "business_name": "Test Shop", "promptpay_id": "0812345678",
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"email": email, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def api_key(client, merchant):
    r = client.post("/dashboard/api-keys", headers=merchant["headers"], json={"name": "test"})
    assert r.status_code == 201, r.text
    return r.json()["secret"]
