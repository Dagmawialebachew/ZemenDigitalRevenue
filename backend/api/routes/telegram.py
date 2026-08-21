from __future__ import annotations

import hmac
from time import perf_counter

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from backend.core.config import get_settings

router = APIRouter(tags=["telegram"])
log = structlog.get_logger(__name__)


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request) -> dict[str, bool]:
    settings = get_settings()
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.telegram_webhook_secret
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid webhook secret",
        )

    bot = request.app.state.bot
    dispatcher = request.app.state.dispatcher
    if bot is None or dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="bot unavailable",
        )

    raw_update = await request.json()
    started = perf_counter()
    try:
        await dispatcher.feed_raw_update(bot, raw_update)
    finally:
        elapsed_ms = round((perf_counter() - started) * 1000, 1)
        callback = raw_update.get("callback_query") or {}
        fields = {
            "update_id": raw_update.get("update_id"),
            "update_kind": "callback" if callback else "message",
            "callback_data": callback.get("data"),
            "elapsed_ms": elapsed_ms,
        }
        if elapsed_ms >= 1000:
            log.warning("telegram_update_slow", **fields)
        else:
            log.info("telegram_update_processed", **fields)
    return {"ok": True}
