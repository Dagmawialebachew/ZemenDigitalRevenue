from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, SendMessage

from bot.services.callbacks import ExpiredCallbackQueryMiddleware, answer_callback_safely


@pytest.mark.asyncio
async def test_expired_callback_does_not_abort_the_handler():
    callback = AsyncMock()
    callback.id = "expired-query"
    callback.data = "sales:preview"
    callback.answer.side_effect = TelegramBadRequest(
        method=callback.answer,
        message="query is too old and response timeout expired or query ID is invalid",
    )

    assert await answer_callback_safely(callback) is False


@pytest.mark.asyncio
async def test_unexpected_callback_error_is_not_hidden():
    callback = AsyncMock()
    callback.answer.side_effect = TelegramBadRequest(
        method=callback.answer,
        message="BUTTON_DATA_INVALID",
    )

    with pytest.raises(TelegramBadRequest, match="BUTTON_DATA_INVALID"):
        await answer_callback_safely(callback)


@pytest.mark.asyncio
async def test_request_middleware_only_absorbs_expired_callback_answers():
    middleware = ExpiredCallbackQueryMiddleware()
    make_request = AsyncMock(
        side_effect=TelegramBadRequest(
            method=AsyncMock(),
            message="query is too old and response timeout expired",
        )
    )
    method = AnswerCallbackQuery(callback_query_id="expired-query")

    assert await middleware(make_request, AsyncMock(), method) is True


@pytest.mark.asyncio
async def test_request_middleware_does_not_hide_other_telegram_failures():
    middleware = ExpiredCallbackQueryMiddleware()
    make_request = AsyncMock(
        side_effect=TelegramBadRequest(
            method=AsyncMock(),
            message="chat not found",
        )
    )
    method = SendMessage(chat_id=123, text="hello")

    with pytest.raises(TelegramBadRequest, match="chat not found"):
        await middleware(make_request, AsyncMock(), method)


def test_sales_callbacks_are_acknowledged_before_database_work():
    source = Path("bot/routers/sales.py").read_text(encoding="utf-8")

    for handler in (
        "choose_sales_product",
        "continue_sales",
        "sales_detail",
        "sales_buy",
    ):
        body = source.split(f"async def {handler}(", 1)[1].split("\n\n@router", 1)[0]
        assert body.index("await answer_callback_safely(callback") < body.index(
            "await load_current_entry_context("
        )


def test_legal_callback_is_acknowledged_before_database_work():
    source = Path("bot/routers/legal.py").read_text(encoding="utf-8")
    body = source.split("async def legal_document(", 1)[1]
    assert body.index("await answer_callback_safely(callback)") < body.index(
        "await load_current_entry_context("
    )
