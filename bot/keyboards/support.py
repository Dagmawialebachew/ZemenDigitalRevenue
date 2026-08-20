from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


def support_ops_keyboard(*, case_public_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="💬 REPLY",
            callback_data=f"ops:support:reply:{case_public_id}",
            style=ButtonStyle.PRIMARY,
        ),
        inline_action(
            text="✅ RESOLVE",
            callback_data=f"ops:support:resolve:{case_public_id}",
            style=ButtonStyle.SUCCESS,
        ),
    )
    return builder.as_markup()
