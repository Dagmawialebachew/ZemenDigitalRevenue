from __future__ import annotations

from fastapi import APIRouter, Request

from backend.repositories.jobs import JobRepository
from shared.constants import AIOGRAM_TARGET, APP_NAME, APP_VERSION, TELEGRAM_BOT_API_TARGET

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict[str, object]:
    return {
        "ok": True,
        "service": APP_NAME,
        "version": APP_VERSION,
        "telegram_bot_api_target": TELEGRAM_BOT_API_TARGET,
        "aiogram_target": AIOGRAM_TARGET,
    }


@router.get("/health/ready")
async def ready(request: Request) -> dict[str, object]:
    db = request.app.state.db
    database_ok = await db.ping() if db is not None else False
    bot_ready = request.app.state.bot is not None
    workers = getattr(request.app.state, "workers", None)
    workers_ready = workers is not None and workers.running
    return {
        "ok": database_ok and bot_ready and workers_ready,
        "bot": bot_ready,
        "database": database_ok,
        "workers": workers_ready,
    }


@router.get("/health/jobs")
async def jobs_health(request: Request) -> dict[str, object]:
    db = request.app.state.db
    if db is None or db.pool is None:
        return {"ok": False, "reason": "database unavailable"}
    metrics = await JobRepository(db).metrics()
    return {"ok": metrics["stale"] == 0, **metrics}
