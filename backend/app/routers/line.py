"""Inbound LINE Messaging API webhook.

LINE's "Verify" button (and every real event) POSTs here. We must return 200
for verification to pass. When a channel secret is configured we validate the
X-Line-Signature header; userIds from follow/message events are logged so they
can be linked to a member's customer_line_id for push notifications.
"""

import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..config import settings

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/line", tags=["line"])


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None),
):
    body = await request.body()

    # Verify the signature when a channel secret is set. LINE signs the "Verify"
    # request too, so a correct secret lets verification pass.
    secret = settings.line_channel_secret
    if secret:
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("ascii")
        if not x_line_signature or not hmac.compare_digest(expected, x_line_signature):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid LINE signature")

    # Best-effort: surface userIds so a member's LINE ID can be captured.
    try:
        payload = json.loads(body or b"{}")
        for ev in payload.get("events", []):
            uid = (ev.get("source") or {}).get("userId")
            if uid and ev.get("type") in ("follow", "message"):
                logger.info("LINE %s event from userId=%s", ev.get("type"), uid)
    except Exception:  # noqa: BLE001  never let parsing fail the 200 response
        logger.exception("failed to parse LINE webhook payload")

    return {"ok": True}
