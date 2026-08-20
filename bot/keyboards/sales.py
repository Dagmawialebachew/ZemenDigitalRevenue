from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


def sales_keyboard(*, language: str, price_br: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if language == "en":
        preview = "👀 Show me what's inside"
        buy = f"💚 Get it · {price_br} Br" if price_br else "💚 I want it"
        question = "🤔 I have a question"
    else:
        preview = "👀 ውስጡን አሳየኝ"
        buy = f"💚 ልግዛ · {price_br} ብር" if price_br else "💚 ልግዛ"
        question = "🤔 አንድ ጥያቄ አለኝ"
    builder.row(
        inline_action(text=preview, callback_data="sales:preview", style=ButtonStyle.PRIMARY)
    )
    builder.row(
        inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS)
    )
    builder.row(
        inline_action(text=question, callback_data="sales:question", style=None)
    )
    return builder.as_markup()


def after_detail_keyboard(*, language: str, price_br: str | None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buy = (
        f"💚 Get it · {price_br} Br" if language == "en" and price_br
        else "💚 I want it" if language == "en"
        else f"💚 ልግዛ · {price_br} ብር" if price_br
        else "💚 ልግዛ"
    )
    builder.row(inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS))
    builder.row(
        inline_action(
            text="↩️ Back" if language == "en" else "↩️ ወደኋላ",
            callback_data="sales:continue",
            style=None,
        )
    )
    return builder.as_markup()
