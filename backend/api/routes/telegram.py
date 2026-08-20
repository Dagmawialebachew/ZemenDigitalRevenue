from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Request, status

from backend.core.config import get_settings

router = APIRouter(tags=["telegram"])


@router.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request) -> dict[str, bool]:
    settings = get_settings()
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.telegram_webhook_secret
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid webhook secret")

    bot = request.app.state.bot
    dispatcher = request.app.state.dispatcher
    if bot is None or dispatcher is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="bot unavailable")

    raw_update = await request.json()
    await dispatcher.feed_raw_update(bot, raw_update)
    return {"ok": True}
