from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup

from bot.keyboards.primitives import inline_action


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_action(
                    text="🇪🇹 በአማርኛ እንቀጥል",
                    callback_data="lang:am",
                    style=ButtonStyle.SUCCESS,
                ),
                inline_action(
                    text="🇬🇧 In English",
                    callback_data="lang:en",
                    style=ButtonStyle.PRIMARY,
                ),
            ]
        ]
    )
