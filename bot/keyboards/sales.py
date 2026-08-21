from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


def sales_keyboard(*, language: str, price_br: str | None, mini_app_url: str = "", profile_complete: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if language == "en":
        preview = "👀 Show me what's inside"
        sample = "📄 Free PDF sample"
        store = "🌐 View in Mini App"
        personalize = "✨ Personalize my recommendation"
        buy = f"💚 Get it · {price_br} Br" if price_br else "💚 I want it"
        question = "🤔 I have a question"
    else:
        preview = "👀 ውስጡን አሳየኝ"
        sample = "📄 ነፃ PDF ናሙና"
        store = "🌐 Mini App ላይ ክፈት"
        personalize = "✨ ምክሩን ለእኔ አስተካክል"
        buy = f"💚 ልግዛ · {price_br} ብር" if price_br else "💚 ልግዛ"
        question = "🤔 አንድ ጥያቄ አለኝ"
    builder.row(
        inline_action(text=preview, callback_data="sales:preview", style=ButtonStyle.PRIMARY)
    )
    sample_row = [inline_action(text=sample, callback_data="sales:sample", style=None)]
    if mini_app_url:
        sample_row.append(InlineKeyboardButton(text=store, web_app=WebAppInfo(url=mini_app_url)))
    builder.row(*sample_row)
    builder.row(
        inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS)
    )
    builder.row(
        inline_action(text=question, callback_data="sales:question", style=None)
    )
    if not profile_complete:
        builder.row(
            inline_action(text=personalize, callback_data="sales:continue", style=None)
        )
    return builder.as_markup()


def after_detail_keyboard(*, language: str, price_br: str | None, mini_app_url: str = "", show_sample: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buy = (
        f"💚 Get it · {price_br} Br" if language == "en" and price_br
        else "💚 I want it" if language == "en"
        else f"💚 ልግዛ · {price_br} ብር" if price_br
        else "💚 ልግዛ"
    )
    builder.row(inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS))
    if show_sample:
        sample = "📄 Free PDF sample" if language == "en" else "📄 ነፃ PDF ናሙና"
        builder.row(inline_action(text=sample, callback_data="sales:sample", style=None))
    if mini_app_url:
        store = "🌐 View in Mini App" if language == "en" else "🌐 Mini App ላይ ክፈት"
        builder.row(InlineKeyboardButton(text=store, web_app=WebAppInfo(url=mini_app_url)))
    builder.row(
        inline_action(
            text="↩️ Back" if language == "en" else "↩️ ወደኋላ",
            callback_data="sales:continue",
            style=None,
        )
    )
    return builder.as_markup()
