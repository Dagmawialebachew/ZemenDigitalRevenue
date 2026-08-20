from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from bot.keyboards.primitives import inline_action


def continue_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            inline_action(
                text="✨ እንጀምር / Let's start",
                callback_data="sales:continue",
                style=ButtonStyle.SUCCESS,
            )
        ]
    ]
    if mini_app_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🛍 Zemen Store",
                    web_app=WebAppInfo(url=mini_app_url),
                    style=ButtonStyle.PRIMARY,
                )
            ]
        )
    rows.append(
        [
            inline_action(
                text="🌐 Change language",
                callback_data="menu:language",
                style=None,
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def home_keyboard(*, mini_app_url: str = "") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if mini_app_url:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🛍 Open Zemen Store",
                    web_app=WebAppInfo(url=mini_app_url),
                    style=ButtonStyle.SUCCESS,
                )
            ]
        )
    rows.extend(
        [
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
    return InlineKeyboardMarkup(inline_keyboard=rows)
