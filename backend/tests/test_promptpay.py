import pytest

from app.promptpay import _crc16, build_payload, validate_promptpay
from app.schemas import MerchantSettingsUpdate, ReceivingAccountCreate, RegisterRequest


def test_crc16_standard_check_value():
    # CRC-16/CCITT-FALSE check value for "123456789"
    assert _crc16("123456789") == "29B1"


def test_payload_is_self_consistent():
    payload = build_payload("0899999999", 100.0)
    assert payload.endswith(_crc16(payload[:-4]))


def test_payload_format_and_fields():
    payload = build_payload("0899999999", 100.0)
    assert payload.startswith("000201010212")          # format + dynamic POI
    assert "0016A000000677010111" in payload            # PromptPay AID
    assert "0066899999999" in payload                   # normalized mobile proxy
    assert "5303764" in payload                          # THB currency
    assert "5406100.00" in payload                       # amount


def test_static_payload_has_no_amount():
    payload = build_payload("0899999999", None)
    assert "000201010211" in payload   # static POI
    assert "54" not in payload[12:40]  # no amount tag near the start


def test_national_id_proxy():
    payload = build_payload("1234567890123", 50.0)
    assert "1234567890123" in payload   # 13-digit tax/national id used as-is


# ---- PromptPay validation (reject malformed ids before they become QRs) ----

@pytest.mark.parametrize("proxy,digits", [
    ("0942519661", "0942519661"),            # 10-digit mobile
    ("094-251-9661", "0942519661"),          # formatting stripped
    ("1100702557380", "1100702557380"),      # 13-digit national/tax id
    ("123456789012345", "123456789012345"),  # 15-digit e-Wallet
])
def test_validate_promptpay_accepts_valid(proxy, digits):
    assert validate_promptpay(proxy) == digits


@pytest.mark.parametrize("proxy", [
    "100702557380",    # 12 digits — the typo that produced an unscannable QR
    "12345",           # too short
    "9942519661",      # 10 digits but no leading 0
    "12345678901234",  # 14 digits
    "",
    None,
])
def test_validate_promptpay_rejects_invalid(proxy):
    with pytest.raises(ValueError):
        validate_promptpay(proxy)


def test_build_payload_rejects_invalid_proxy():
    with pytest.raises(ValueError):
        build_payload("100702557380", 1.00)


def test_schema_rejects_invalid_promptpay():
    for make in (
        lambda: RegisterRequest(email="a@b.co", password="secret1",
                                business_name="X", promptpay_id="100702557380"),
        lambda: MerchantSettingsUpdate(promptpay_id="100702557380"),
        lambda: ReceivingAccountCreate(name="main", promptpay_id="100702557380"),
    ):
        with pytest.raises(ValueError):
            make()


def test_schema_allows_valid_and_none():
    assert MerchantSettingsUpdate(promptpay_id="1100702557380").promptpay_id == "1100702557380"
    assert MerchantSettingsUpdate(promptpay_id=None).promptpay_id is None
    assert RegisterRequest(email="a@b.co", password="secret1",
                           business_name="X").promptpay_id is None
