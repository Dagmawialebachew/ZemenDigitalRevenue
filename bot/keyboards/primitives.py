from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, KeyboardButton


# Telegram Bot API 9.4+ supports native button styles. Native clients decide the
# exact shade; arbitrary Zemen hex backgrounds are not available on bot keyboards.

def inline_action(
    *,
    text: str,
    callback_data: str | None = None,
    url: str | None = None,
    style: ButtonStyle | None = ButtonStyle.SUCCESS,
    icon_custom_emoji_id: str | None = None,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )


def reply_action(
    *,
    text: str,
    style: ButtonStyle | None = ButtonStyle.PRIMARY,
    icon_custom_emoji_id: str | None = None,
) -> KeyboardButton:
    return KeyboardButton(
        text=text,
        style=style,
        icon_custom_emoji_id=icon_custom_emoji_id,
    )
