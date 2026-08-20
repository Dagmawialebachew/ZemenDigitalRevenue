from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.onboarding import OnboardingProgress, OnboardingService
from bot.keyboards.onboarding import onboarding_keyboard
from bot.services.current_user import load_current_entry_context
from bot.services.onboarding_copy import completion_text, question_text

router = Router(name="onboarding")


async def send_onboarding_step(
    *,
    message: Message,
    db: Database,
    user_id: object,
) -> OnboardingProgress:
    progress = await OnboardingService(db).resume(user_id=user_id)
    if progress.completed:
        await message.answer(
            completion_text(
                first_name=progress.first_name,
                language=progress.language,
                profile=progress.profile,
            )
        )
        return progress

    await message.answer(
        question_text(
            field=progress.next_field,
            language=progress.language,
            profile=progress.profile,
        ),
        reply_markup=onboarding_keyboard(
            field=progress.next_field,
            language=progress.language,
            role=progress.profile.role,
        ),
    )
    return progress


@router.callback_query(F.data.startswith("ob:"))
async def answer_onboarding(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please send /start again.", show_alert=True)
        return
    try:
        _, field, value = (callback.data or "").split(":", 2)
        progress = await OnboardingService(db).answer(
            user_id=current.user_id,
            field=field,
            value=value,
        )
    except (ValueError, LookupError):
        await callback.answer("That step changed. Tap /start and continue.", show_alert=True)
        return

    await callback.answer("✅")
    if progress.completed:
        await callback.message.edit_text(
            completion_text(
                first_name=progress.first_name,
                language=progress.language,
                profile=progress.profile,
            )
        )
        # Imported lazily to keep the router modules independent.
        from bot.routers.sales import send_sales_pitch

        await send_sales_pitch(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=progress.user_id,
        )
        return

    await callback.message.edit_text(
        question_text(
            field=progress.next_field,
            language=progress.language,
            profile=progress.profile,
        ),
        reply_markup=onboarding_keyboard(
            field=progress.next_field,
            language=progress.language,
            role=progress.profile.role,
        ),
    )
