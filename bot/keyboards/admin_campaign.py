from __future__ import annotations

from decimal import Decimal
from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


def discount_control_card_keyboard(
    *,
    price_br: int | Decimal,
    slug: str,
) -> InlineKeyboardMarkup:
    """Builds interactive action buttons for the /discount control card."""
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="👁 Send Preview to Me",
            callback_data=f"admin:disc:preview:{price_br}:{slug}",
            style=ButtonStyle.PRIMARY,
        )
    )
    builder.row(
        inline_action(
            text="🚀 Launch Campaign",
            callback_data=f"admin:disc:launch:{price_br}:{slug}",
            style=ButtonStyle.SUCCESS,
        ),
        inline_action(
            text="❌ Cancel",
            callback_data="admin:disc:cancel",
            style=ButtonStyle.DANGER,
        ),
    )
    return builder.as_markup()


def discount_preview_cta_keyboard(
    *,
    price_br: int | Decimal,
) -> InlineKeyboardMarkup:
    """Builds customer-facing buy CTA for admin preview."""
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text=f"🔥 አሁን ይግዙ — {price_br} ብር",
            callback_data="sales:buy",
            style=ButtonStyle.SUCCESS,
        )
    )
    return builder.as_markup()
