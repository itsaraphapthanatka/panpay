from app.promptpay import _crc16, build_payload


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
