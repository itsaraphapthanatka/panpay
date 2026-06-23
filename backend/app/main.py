import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import auth, charges, checkout, dashboard, embed, membership, portal

# Use uvicorn's logger so scheduler messages appear in the server logs.
logger = logging.getLogger("uvicorn.error")


def _run_renewals_once() -> dict:
    from .database import SessionLocal
    from .jobs import run_due_renewals

    db = SessionLocal()
    try:
        return run_due_renewals(db)
    finally:
        db.close()


async def _scheduler_loop() -> None:
    interval = max(1, settings.scheduler_interval_hours) * 3600
    while True:
        await asyncio.sleep(interval)
        try:
            summary = await anyio.to_thread.run_sync(_run_renewals_once)
            logger.info("renewal job ran: %s", summary)
        except Exception:  # never let a job error kill the loop
            logger.exception("renewal job failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    task = None
    if settings.run_scheduler:
        logger.info("starting in-process renewal scheduler (every %sh)", settings.scheduler_interval_hours)
        task = asyncio.create_task(_scheduler_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="PanPay Gateway",
    description="A PromptPay payment gateway with slip verification (paynoi-style).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "slip_provider": settings.slip_provider}


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(charges.router)
app.include_router(checkout.router)
app.include_router(embed.router)
app.include_router(membership.router)
app.include_router(portal.router)
