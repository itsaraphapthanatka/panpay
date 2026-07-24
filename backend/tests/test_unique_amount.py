"""Unit tests for unique-satang charge matching (charge_ops.unique_payable_amount).

These exercise the helper directly against the DB session, so they don't touch
the billing/credit gate on the charge-creation API.
"""

from datetime import timedelta

import pytest

from app.charge_ops import unique_payable_amount
from app.config import settings
from app.database import SessionLocal
from app.models import Charge, Merchant, utcnow


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def merchant_row(db):
    m = Merchant(
        email="uniq@panpay.io",
        password_hash="x",
        business_name="Uniq Shop",
        promptpay_id="0812345678",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _pending(db, merchant, amount, minutes_ago=0):
    c = Charge(
        merchant_id=merchant.id,
        amount=amount,
        status="pending",
        promptpay_payload="x",
        created_at=utcnow() - timedelta(minutes=minutes_ago),
    )
    db.add(c)
    db.commit()
    return c


def test_returns_base_when_feature_off(db, merchant_row, monkeypatch):
    monkeypatch.setattr(settings, "unique_amount_matching", False)
    _pending(db, merchant_row, 100.00)
    assert unique_payable_amount(db, merchant_row, 100.00) == 100.00


def test_unique_when_no_collision(db, merchant_row, monkeypatch):
    monkeypatch.setattr(settings, "unique_amount_matching", True)
    assert unique_payable_amount(db, merchant_row, 100.00) == 100.00


def test_nudges_on_collision(db, merchant_row, monkeypatch):
    monkeypatch.setattr(settings, "unique_amount_matching", True)
    _pending(db, merchant_row, 100.00)
    assert unique_payable_amount(db, merchant_row, 100.00) == 100.01


def test_finds_next_free_satang(db, merchant_row, monkeypatch):
    monkeypatch.setattr(settings, "unique_amount_matching", True)
    _pending(db, merchant_row, 100.00)
    _pending(db, merchant_row, 100.01)
    _pending(db, merchant_row, 100.02)
    assert unique_payable_amount(db, merchant_row, 100.00) == 100.03


def test_ignores_paid_and_old_charges(db, merchant_row, monkeypatch):
    monkeypatch.setattr(settings, "unique_amount_matching", True)
    # A paid charge at the same amount must not block reuse.
    paid = _pending(db, merchant_row, 100.00)
    paid.status = "paid"
    db.commit()
    # A pending charge older than the 24h window must not block reuse.
    _pending(db, merchant_row, 100.00, minutes_ago=25 * 60)
    assert unique_payable_amount(db, merchant_row, 100.00) == 100.00
