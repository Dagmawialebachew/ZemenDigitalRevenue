from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, WebAppInfo

from bot.keyboards.primitives import inline_action


def welcome_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_action(
                    text="✨ Continue",
                    callback_data="foundation:continue",
                    style=ButtonStyle.PRIMARY,
                )
            ]
        ]
    )
