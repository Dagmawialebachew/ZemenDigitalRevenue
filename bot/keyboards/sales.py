from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


def sales_keyboard(*, language: str, price_br: str | None, mini_app_url: str = "", profile_complete: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if language == "en":
        buy = f"💚 Buy Now · {price_br} Br" if price_br else "💚 Buy Now"
        sample = "📄 Free Sample"
        preview = "👀 Preview Inside"
        question = "🤔 Ask Question"
    else:
        buy = f"💚 አሁን ይግዙ · {price_br} ብር" if price_br else "💚 አሁን ይግዙ"
        sample = "📄 ነፃ Sample"
        preview = "👀 ውስጡን ይመልከቱ"
        question = "🤔 ጥያቄ አለኝ"

    # 2x2 Grid Layout
    builder.row(
        inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS),
        inline_action(text=sample, callback_data="sales:sample", style=None),
    )
    builder.row(
        inline_action(text=preview, callback_data="sales:preview", style=ButtonStyle.PRIMARY),
        inline_action(text=question, callback_data="sales:question", style=None),
    )
    return builder.as_markup()


def after_detail_keyboard(
    *,
    language: str,
    price_br: str | None,
    mini_app_url: str = "",
    show_sample: bool = True,
    show_support: bool = False,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buy = (
        f"💚 Buy Now · {price_br} Br" if language == "en" and price_br
        else "💚 Buy Now" if language == "en"
        else f"💚 አሁን ይግዙ · {price_br} ብር" if price_br
        else "💚 አሁን ይግዙ"
    )
    builder.row(inline_action(text=buy, callback_data="sales:buy", style=ButtonStyle.SUCCESS))
    
    actions: list[InlineKeyboardButton] = []
    if show_sample:
        sample = "📄 Free Sample" if language == "en" else "📄 ነፃ Sample"
        actions.append(inline_action(text=sample, callback_data="sales:sample", style=None))
    if show_support:
        support = "💬 Ask Support" if language == "en" else "💬 አስተዳዳሪን ያውሩ"
        actions.append(inline_action(text=support, callback_data="menu:help", style=ButtonStyle.PRIMARY))
    
    actions.append(
        inline_action(
            text="↩️ Back" if language == "en" else "↩️ ወደኋላ",
            callback_data="sales:continue",
            style=None,
        )
    )
    builder.row(*actions)
    return builder.as_markup()


def tier_selection_keyboard(
    *,
    language: str,
    product_slug: str = "ai-kezero",
    standard_price: str = "549",
    pro_price: str = "1299",
    vip_price: str = "2499",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if language == "en":
        t1 = f"📘 Standard ({standard_price} Br) · Complete Guide"
        t2 = f"🚀 Pro Bundle ({pro_price} Br) · Guide + 27 Prompts + Videos"
        t3 = f"👑 VIP Masterpack ({vip_price} Br) · All + VIP Consultation"
        back = "↩️ Back"
    else:
        t1 = f"📘 Standard ({standard_price} ብር) · 131-ገጽ መጽሐፍ"
        t2 = f"🚀 Pro Bundle ({pro_price} ብር) · መጽሐፍ + 27+ Prompts + Videos"
        t3 = f"👑 VIP Masterpack ({vip_price} ብር) · ሁሉም + VIP Consultation"
        back = "↩️ ወደኋላ"
    builder.row(inline_action(text=t1, callback_data=f"sales:tier:standard:{product_slug}", style=ButtonStyle.PRIMARY))
    builder.row(inline_action(text=t2, callback_data=f"sales:tier:pro:{product_slug}", style=ButtonStyle.SUCCESS))
    builder.row(inline_action(text=t3, callback_data=f"sales:tier:vip:{product_slug}", style=ButtonStyle.SUCCESS))
    builder.row(inline_action(text=back, callback_data="sales:continue", style=None))
    return builder.as_markup()

