"""Lightweight in-memory fixed-window rate limiting.

Good enough for a single process / local dev. For multi-instance production,
back this with Redis (swap the _store + _check internals).
"""

import time

from fastapi import HTTPException, Request, status

# key -> (window_start_monotonic, count)
_store: dict[str, tuple[float, int]] = {}


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _check(key: str, limit: int, window: int = 60) -> None:
    now = time.monotonic()
    start, count = _store.get(key, (now, 0))
    if now - start >= window:
        start, count = now, 0
    count += 1
    _store[key] = (start, count)
    if count > limit:
        retry = int(window - (now - start)) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded. Slow down.",
            headers={"Retry-After": str(retry)},
        )


def _api_bucket(request: Request) -> str:
    key = request.headers.get("x-api-key")
    if not key:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer ") and "sk_" in auth:
            key = auth.split(" ", 1)[1].strip()
    return key[:20] if key else (client_ip(request) or "unknown")


# --- FastAPI dependencies (attach with Depends) ---
def limit_auth(request: Request) -> None:
    _check(f"auth:{client_ip(request) or 'unknown'}", limit=20, window=60)


def limit_slip(request: Request) -> None:
    _check(f"slip:{client_ip(request) or 'unknown'}", limit=30, window=60)


def limit_api(request: Request) -> None:
    _check(f"api:{_api_bucket(request)}", limit=120, window=60)
