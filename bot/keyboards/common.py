from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, WebAppInfo

from bot.keyboards.primitives import inline_action


def welcome_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    rows = []
    if mini_app_url:
        # WebAppInfo is created directly because our primitive intentionally
        # accepts only callback/url actions. Mini App buttons get the same native style.
        from aiogram.types import InlineKeyboardButton

        rows.append([
            InlineKeyboardButton(
                text="🛍 Open Zemen Store",
                web_app=WebAppInfo(url=mini_app_url),
                style=ButtonStyle.SUCCESS,
            )
        ])
    rows.append([
        inline_action(
            text="✨ Continue",
            callback_data="foundation:continue",
            style=ButtonStyle.PRIMARY,
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
