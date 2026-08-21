from __future__ import annotations

from typing import Any

import structlog
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery
from aiogram.types import CallbackQuery

log = structlog.get_logger(__name__)

_EXPIRED_QUERY_ERRORS = (
    "query is too old",
    "query id is invalid",
    "response timeout expired",
)


def _is_expired_callback_error(exc: TelegramBadRequest) -> bool:
    error = str(exc).lower()
    return any(fragment in error for fragment in _EXPIRED_QUERY_ERRORS)


class ExpiredCallbackQueryMiddleware:
    """Keep an expired answerCallbackQuery call from aborting its handler."""

    async def __call__(
        self,
        make_request: Any,
        bot: Any,
        method: Any,
    ) -> Any:
        try:
            return await make_request(bot, method)
        except TelegramBadRequest as exc:
            if not isinstance(method, AnswerCallbackQuery) or not _is_expired_callback_error(exc):
                raise
            log.info(
                "expired_callback_ignored",
                callback_id=method.callback_query_id,
            )
            return True


async def answer_callback_safely(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool | None = None,
) -> bool:
    """Acknowledge a Telegram button without crashing on an expired query.

    Render can be unavailable while deploying or waking. Telegram may then
    deliver a callback after its acknowledgement window has expired. The
    business action should still finish and the webhook must return success so
    Telegram does not retry the same update indefinitely.
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        if not _is_expired_callback_error(exc):
            raise
        log.info(
            "expired_callback_ignored",
            callback_id=callback.id,
            callback_data=callback.data,
        )
        return False
    return True
