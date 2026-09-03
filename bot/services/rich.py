from __future__ import annotations

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InputRichMessage, InlineKeyboardMarkup, Message

log = structlog.get_logger(__name__)


async def send_rich_or_fallback(
    bot: Bot,
    *,
    chat_id: int,
    markdown: str,
    fallback_text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    enabled: bool = True,
) -> Message:
    """Use Bot API 10.x Rich Messages if available on bot, with a normal message fallback.

    Rich Messages are a presentation enhancement, never a business dependency.
    """
    if enabled and hasattr(bot, "send_rich_message"):
        try:
            return await bot.send_rich_message(
                chat_id=chat_id,
                rich_message=InputRichMessage(markdown=markdown),
                reply_markup=reply_markup,
            )
        except Exception as exc:
            log.warning("rich_message_fallback", error=str(exc))

    return await bot.send_message(
        chat_id=chat_id,
        text=fallback_text,
        reply_markup=reply_markup,
    )
