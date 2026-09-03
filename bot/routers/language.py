from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.types import CallbackQuery

from backend.core.config import Settings
from backend.db.pool import Database
from bot.keyboards.language import language_keyboard
from bot.services.copy import after_language
from bot.services.current_user import load_current_entry_context
from bot.services.profile import CustomerProfileService
from bot.services.rich import send_rich_or_fallback

router = Router(name="language")


@router.callback_query(F.data.in_({"lang:am", "lang:en"}))
async def choose_language(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    language = "am" if callback.data == "lang:am" else "en"
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please send /start again.", show_alert=True)
        return

    await CustomerProfileService(db).set_language(user_id=current.user_id, language=language)
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please send /start again.", show_alert=True)
        return

    await callback.answer("✅")
    if callback.message:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)

    chat_id = callback.message.chat.id if callback.message else callback.from_user.id
    from aiogram.enums import ChatAction
    import asyncio
    with suppress(Exception):
        await callback.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await asyncio.sleep(1.2)

    if (
        callback.message
        and not current.profile_completed
        and current.requires_onboarding_before_sales
    ):
        from bot.routers.onboarding import send_onboarding_step

        await send_onboarding_step(
            message=callback.message,
            db=db,
            user_id=current.user_id,
            campaign_product_title=current.focus_product_title,
        )
        return

    if callback.message:
        from bot.routers.sales import send_sales_pitch

        await send_sales_pitch(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
        )


@router.callback_query(F.data == "menu:language")
async def change_language(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "🌐 ቋንቋ / Language",
            reply_markup=language_keyboard(),
        )
