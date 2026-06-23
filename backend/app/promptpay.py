"""Generate PromptPay QR payloads following the EMVCo / Thai QR standard."""

import base64
from io import BytesIO

import qrcode

AID_PROMPTPAY = "A000000677010111"


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16(payload: str) -> str:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in payload.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def _format_proxy(proxy: str) -> tuple[str, str]:
    """Return (sub_tag, value) for the merchant account info block."""
    digits = "".join(c for c in proxy if c.isdigit())
    if len(digits) >= 15:
        # e-Wallet id
        return "03", digits
    if len(digits) == 13:
        # National ID / Tax ID
        return "02", digits
    # Mobile number -> 0066 + 9 digit local number (drop leading 0)
    local = digits[1:] if digits.startswith("0") else digits
    return "01", "0066" + local


def build_payload(proxy: str, amount: float | None = None) -> str:
    sub_tag, value = _format_proxy(proxy)
    merchant_info = _tlv("00", AID_PROMPTPAY) + _tlv(sub_tag, value)

    payload = _tlv("00", "01")
    # Point of initiation: 11 = static (reusable), 12 = dynamic (amount fixed, one-time)
    payload += _tlv("01", "12" if amount is not None else "11")
    payload += _tlv("29", merchant_info)
    payload += _tlv("53", "764")  # THB
    if amount is not None:
        payload += _tlv("54", f"{float(amount):.2f}")
    payload += _tlv("58", "TH")
    payload += "6304"  # CRC tag + length, value computed over everything before it
    payload += _crc16(payload)
    return payload


def payload_to_data_uri(payload: str) -> str:
    """Render a QR payload to a base64 PNG data URI for embedding in <img>."""
    img = qrcode.make(payload)
    buf = BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
