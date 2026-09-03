from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.keyboards.primitives import inline_action


def continue_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_action(
                    text="✨ እንጀምር / Start",
                    callback_data="sales:continue",
                    style=ButtonStyle.SUCCESS,
                ),
                inline_action(
                    text="🌐 Language / ቋንቋ",
                    callback_data="menu:language",
                    style=None,
                ),
            ]
        ]
    )


def home_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                inline_action(
                    text="📚 My Library",
                    callback_data="menu:library",
                    style=ButtonStyle.PRIMARY,
                ),
                inline_action(
                    text="🤝 Earn",
                    callback_data="menu:earn",
                    style=ButtonStyle.SUCCESS,
                ),
            ],
            [
                inline_action(
                    text="💬 Help",
                    callback_data="menu:help",
                    style=None,
                ),
                inline_action(
                    text="🌐 Language",
                    callback_data="menu:language",
                    style=None,
                ),
            ],
        ]
    )
