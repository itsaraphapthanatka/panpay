"""Decode the QR code embedded in a Thai bank transfer slip image.

Thai bank slips carry a "slip verification" QR (Thai Bankers' Association format)
whose payload uniquely identifies the transfer. We read it locally with OpenCV so
the customer only has to upload the slip — no manual reference entry. The decoded
payload is the canonical, globally-unique reference for that transaction, which is
exactly what both our duplicate-slip guard and the verification APIs need.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2

    _CV2_AVAILABLE = True
except Exception:  # pragma: no cover - opencv missing
    _CV2_AVAILABLE = False


def _load_image(image_bytes: bytes):
    arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def decode_qr(image_bytes: bytes) -> str | None:
    """Return the decoded QR payload string, or None if no QR could be read."""
    if not _CV2_AVAILABLE or not image_bytes:
        return None
    img = _load_image(image_bytes)
    if img is None:
        return None

    detector = cv2.QRCodeDetector()

    # 1) straight decode
    data, _, _ = detector.detectAndDecode(img)
    if data:
        return data

    # 2) grayscale + multi-detect (helps with photographed / multi-code slips)
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ok, infos, _, _ = detector.detectAndDecodeMulti(gray)
        if ok:
            for s in infos:
                if s:
                    return s
    except cv2.error:
        pass

    # 3) upscale once more for small QRs
    try:
        big = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        data, _, _ = detector.detectAndDecode(big)
        if data:
            return data
    except cv2.error:
        pass

    return None


def parse_slip_qr(payload: str) -> dict:
    """Best-effort EMVCo-style TLV parse of a slip QR into a {tag: value} dict.

    The exact sub-field semantics vary by bank, so callers should treat the full
    payload string as the canonical reference and use these fields only for display.
    """
    out: dict[str, str] = {}
    i = 0
    try:
        while i + 4 <= len(payload):
            tag = payload[i : i + 2]
            length = int(payload[i + 2 : i + 4])
            i += 4
            out[tag] = payload[i : i + length]
            i += length
    except (ValueError, IndexError):
        pass
    return out
