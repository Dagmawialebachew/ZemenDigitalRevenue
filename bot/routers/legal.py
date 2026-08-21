from __future__ import annotations

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from backend.db.pool import Database
from backend.domain.policies import policy_html
from bot.keyboards.payments import purchase_policy_keyboard
from bot.keyboards.primitives import inline_action
from bot.services.callbacks import answer_callback_safely
from bot.services.current_user import load_current_entry_context


router = Router(name="legal")


def _policy_help_keyboard(kind: str, language: str) -> InlineKeyboardMarkup | None:
    if kind == "refund":
        return InlineKeyboardMarkup(inline_keyboard=[[
            inline_action(
                text="Request refund support" if language == "en" else "የተመላሽ ጥያቄ ይክፈቱ",
                callback_data="support:category:refund_request",
                style=ButtonStyle.PRIMARY,
            )
        ]])
    if kind == "delivery":
        return InlineKeyboardMarkup(inline_keyboard=[[
            inline_action(
                text="Report missing delivery" if language == "en" else "ያልደረሰ ምርት ያሳውቁ",
                callback_data="support:category:missing_delivery",
                style=ButtonStyle.PRIMARY,
            )
        ]])
    return None


async def _language(message: Message, db: Database) -> str:
    if message.from_user is None:
        return "am"
    current = await load_current_entry_context(db, telegram_user=message.from_user)
    return current.language_for_copy if current else "am"


@router.message(Command("terms"))
async def terms_command(message: Message, db: Database) -> None:
    if message.chat.type != "private":
        raise SkipHandler
    language = await _language(message, db)
    await message.answer(policy_html("terms", language), reply_markup=_policy_help_keyboard("terms", language))


@router.message(Command("privacy"))
async def privacy_command(message: Message, db: Database) -> None:
    if message.chat.type != "private":
        raise SkipHandler
    language = await _language(message, db)
    await message.answer(policy_html("privacy", language), reply_markup=_policy_help_keyboard("privacy", language))


@router.message(Command("refund"))
async def refund_command(message: Message, db: Database) -> None:
    if message.chat.type != "private":
        raise SkipHandler
    language = await _language(message, db)
    await message.answer(policy_html("refund", language), reply_markup=_policy_help_keyboard("refund", language))


@router.message(Command("delivery"))
async def delivery_command(message: Message, db: Database) -> None:
    if message.chat.type != "private":
        raise SkipHandler
    language = await _language(message, db)
    await message.answer(policy_html("delivery", language), reply_markup=_policy_help_keyboard("delivery", language))


@router.callback_query(F.data.startswith("legal:"))
async def legal_document(callback: CallbackQuery, db: Database) -> None:
    if callback.message is None or callback.data is None:
        await answer_callback_safely(callback)
        return
    parts = callback.data.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"terms", "refund", "privacy", "delivery"}:
        await answer_callback_safely(callback, "Document unavailable", show_alert=True)
        return
    await answer_callback_safely(callback)
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    language = current.language_for_copy if current else "am"
    order_public_id = parts[2]
    await callback.message.answer(
        policy_html(parts[1], language),
        reply_markup=(
            purchase_policy_keyboard(order_public_id=order_public_id, language=language)
            if order_public_id != "none" else _policy_help_keyboard(parts[1], language)
        ),
    )
