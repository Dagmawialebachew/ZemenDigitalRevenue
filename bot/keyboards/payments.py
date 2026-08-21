from __future__ import annotations

from aiogram.enums import ButtonStyle
from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards.primitives import inline_action


REJECT_REASON_LABELS = {
    "wrong_amount": "💰 Wrong amount",
    "wrong_receiver": "👤 Wrong receiver",
    "unclear_screenshot": "📸 Screenshot unclear",
    "old_transaction": "🕐 Old transaction",
    "duplicate_receipt": "♻️ Duplicate receipt",
    "transaction_not_found": "🔎 Transaction not found",
    "other": "✏️ Other",
}


def payment_method_keyboard(
    *,
    order_public_id: str,
    language: str,
    cbe_enabled: bool,
    telebirr_enabled: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if cbe_enabled:
        builder.row(
            inline_action(
                text="🏦 CBE",
                callback_data=f"pay:method:{order_public_id}:cbe",
                style=ButtonStyle.PRIMARY,
            )
        )
    if telebirr_enabled:
        builder.row(
            inline_action(
                text="📱 Telebirr",
                callback_data=f"pay:method:{order_public_id}:telebirr",
                style=ButtonStyle.PRIMARY,
            )
        )
    builder.row(
        inline_action(
            text="↩️ Back" if language == "en" else "↩️ ወደኋላ",
            callback_data="sales:continue",
            style=None,
        )
    )
    return builder.as_markup()


def purchase_policy_keyboard(*, order_public_id: str, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="📜 Terms" if language == "en" else "📜 የግዢ ውሎች",
            callback_data=f"legal:terms:{order_public_id}",
            style=None,
        ),
        inline_action(
            text="↩️ Refunds" if language == "en" else "↩️ Refund policy",
            callback_data=f"legal:refund:{order_public_id}",
            style=None,
        ),
    )
    builder.row(
        inline_action(
            text="✅ I understand and agree" if language == "en" else "✅ አንብቤ ተስማምቻለሁ",
            callback_data=f"pay:accept:{order_public_id}",
            style=ButtonStyle.SUCCESS,
        )
    )
    builder.row(
        inline_action(
            text="💬 Ask before paying" if language == "en" else "💬 ከመክፈልዎ በፊት ይጠይቁ",
            callback_data="menu:help",
            style=None,
        )
    )
    return builder.as_markup()


def payment_instructions_keyboard(
    *,
    payment_public_id: str,
    destination: str,
    amount_text: str,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Bot API 10.x native copy-to-clipboard buttons keep sensitive/manual-payment
    # actions one tap without relying on JavaScript or a Mini App clipboard hack.
    builder.row(
        InlineKeyboardButton(
            text="📋 Copy account" if language == "en" else "📋 አካውንት ኮፒ አድርግ",
            copy_text=CopyTextButton(text=destination),
            style=ButtonStyle.PRIMARY,
        ),
        InlineKeyboardButton(
            text="💰 Copy amount" if language == "en" else "💰 መጠን ኮፒ አድርግ",
            copy_text=CopyTextButton(text=amount_text),
            style=ButtonStyle.PRIMARY,
        ),
    )
    builder.row(
        inline_action(
            text="✅ I've Paid" if language == "en" else "✅ ከፍያለሁ",
            callback_data=f"pay:paid:{payment_public_id}",
            style=ButtonStyle.SUCCESS,
        )
    )
    return builder.as_markup()


def payment_followup_keyboard(
    *,
    order_public_id: str,
    language: str,
    state: str = "review",
    mini_app_url: str = "",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if state == "owned":
        if mini_app_url:
            separator = "&" if "?" in mini_app_url else "?"
            builder.row(
                InlineKeyboardButton(
                    text="📚 Open Library & review" if language == "en" else "📚 Library ክፈቱና አስተያየት ይስጡ",
                    web_app=WebAppInfo(url=f"{mini_app_url}{separator}section=library"),
                    style=ButtonStyle.SUCCESS,
                )
            )
        else:
            builder.row(
                inline_action(
                    text="📚 Open My Library" if language == "en" else "📚 Libraryዎን ይክፈቱ",
                    callback_data="menu:library",
                    style=ButtonStyle.SUCCESS,
                )
            )
    else:
        label = (
            "📸 Send a new screenshot"
            if state == "rejected" and language == "en"
            else "📸 አዲስ screenshot ይላኩ"
            if state == "rejected"
            else "🔄 Check payment status"
            if language == "en"
            else "🔄 የክፍያውን ሁኔታ ይፈትሹ"
        )
        builder.row(
            inline_action(
                text=label,
                callback_data=f"pay:status:{order_public_id}",
                style=ButtonStyle.PRIMARY,
            )
        )
    builder.row(
        inline_action(
            text="💬 Get help" if language == "en" else "💬 እገዛ ያግኙ",
            callback_data="menu:help",
            style=None,
        )
    )
    return builder.as_markup()


def external_checkout_keyboard(*, url: str, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="↗️ Continue to checkout" if language == "en" else "↗️ ወደ ክፍያ ቀጥል",
            url=url,
            style=ButtonStyle.SUCCESS,
        )
    )
    return builder.as_markup()


def payment_review_keyboard(*, payment_public_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="✅ APPROVE",
            callback_data=f"ops:pay:approve:{payment_public_id}",
            style=ButtonStyle.SUCCESS,
        ),
        inline_action(
            text="❌ REJECT",
            callback_data=f"ops:pay:reject:{payment_public_id}",
            style=ButtonStyle.DANGER,
        ),
    )
    builder.row(
        inline_action(
            text="⚠️ FLAG",
            callback_data=f"ops:pay:flag:{payment_public_id}",
            style=ButtonStyle.PRIMARY,
        )
    )
    return builder.as_markup()


def payment_reject_reason_keyboard(*, payment_public_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in REJECT_REASON_LABELS.items():
        builder.row(
            inline_action(
                text=label,
                callback_data=f"ops:pay:reason:{payment_public_id}:{code}",
                style=ButtonStyle.DANGER if code != "other" else None,
            )
        )
    builder.row(
        inline_action(
            text="↩️ Back to review",
            callback_data=f"ops:pay:review:{payment_public_id}",
            style=ButtonStyle.PRIMARY,
        )
    )
    return builder.as_markup()
