from __future__ import annotations

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.operations import OperationsService
from bot.services.current_user import load_current_entry_context


router = Router(name="fallback")


def _fallback_keyboard(language: str) -> InlineKeyboardMarkup:
    home_text = "🏠 Home" if language == "en" else "🏠 ዋና ገጽ"
    support_text = "💬 Support" if language == "en" else "💬 Support"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=home_text,
                    callback_data="menu:home",
                ),
                InlineKeyboardButton(
                    text=support_text,
                    callback_data="menu:help",
                ),
            ]
        ]
    )


def _attachment_from_message(message: Message) -> dict[str, object] | None:
    if message.photo:
        photo = message.photo[-1]
        return {
            "type": "photo",
            "telegram_file_id": photo.file_id,
            "telegram_file_unique_id": photo.file_unique_id,
        }

    if message.document:
        document = message.document
        return {
            "type": "document",
            "telegram_file_id": document.file_id,
            "telegram_file_unique_id": document.file_unique_id,
            "file_name": document.file_name,
            "mime_type": document.mime_type,
        }

    return None


@router.message(
    F.text | F.photo | F.document,
    F.chat.type == "private",
)
async def unhandled_customer_message(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return

    current = await load_current_entry_context(
        db,
        telegram_user=message.from_user,
    )

    if current is None:
        await message.answer("👋 Send /start first.")
        return

    service = OperationsService(db, settings)

    # Anything that reaches this final router was not consumed by the
    # normal start/onboarding/sales/payment/support/menu flows.
    # Open or reuse Support and preserve the original customer message.
    await service.open_support(
        user_id=current.user_id,
    )

    try:
        result = await service.submit_support_message(
            user_id=current.user_id,
            telegram_message_id=message.message_id,
            body=message.text or message.caption,
            attachment=_attachment_from_message(message),
        )
    except LookupError:
        if current.language_for_copy == "en":
            await message.answer(
                "⚠️ We couldn't send that to Support right now. Please try again."
            )
        else:
            await message.answer(
                "⚠️ መልዕክትዎን ወደ Support መላክ አልቻልንም። እባክዎ እንደገና ይሞክሩ።"
            )
        return

    language = current.language_for_copy

    if language == "en":
        text = (
            "✅ <b>Our team received your message.</b>\n\n"
            f"Support case: <code>{result['case_public_id']}</code>\n\n"
            "It has been sent to Zemen Support. You can keep using the buttons below, "
            "or stay here and wait for our reply."
        )
    else:
        text = (
            "✅ <b>መልዕክትዎ ደርሶናል።</b>\n\n"
            f"Support case: <code>{result['case_public_id']}</code>\n\n"
            "መልዕክትዎ ወደ Zemen Support ቡድናችን ተልኳል። "
            "ከታች ያሉትን ቁልፎች በመጠቀም botን መቀጠል "
            "ወይም የSupport ምላሽን እዚሁ መጠበቅ ይችላሉ።"
        )

    await message.answer(
        text,
        reply_markup=_fallback_keyboard(language),
    )
