from __future__ import annotations

import structlog
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.customer_entry import CustomerEntryService
from bot.keyboards.home import continue_keyboard
from bot.keyboards.language import language_keyboard
from bot.services.copy import language_prompt, returning_prompt
from bot.services.rich import send_rich_or_fallback
from shared.deeplinks import StartKind, parse_start_payload

router = Router(name="start")
log = structlog.get_logger(__name__)


@router.message(CommandStart())
async def start(
    message: Message,
    command: CommandObject,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return

    entry = await CustomerEntryService(db).enter(
        telegram_user=message.from_user,
        start=parse_start_payload(command.args),
    )

    log.info(
        "bot_started",
        telegram_user_id=entry.telegram_id,
        zemen_user_id=str(entry.user_id),
        start_kind=entry.start_kind.value,
        source=entry.source_name,
        creative=entry.creative,
        focus_product_id=str(entry.focus_product_id) if entry.focus_product_id else None,
        new_user=entry.is_new_user,
    )

    if entry.start_kind == StartKind.ORDER and entry.start_token:
        from bot.routers.payments import send_order_resume

        try:
            await send_order_resume(
                message=message,
                db=db,
                settings=settings,
                user_id=entry.user_id,
                order_public_id=entry.start_token,
            )
        except (LookupError, ValueError):
            await message.answer(
                "⚠️ This order link is no longer active."
                if entry.language_for_copy == "en"
                else "⚠️ ይህ የትዕዛዝ link ከእንግዲህ አይሰራም።"
            )
        return

    if entry.preferred_language is None:
        copy = language_prompt(entry)
        await send_rich_or_fallback(
            message.bot,
            chat_id=message.chat.id,
            markdown=copy.rich_markdown,
            fallback_text=copy.text,
            reply_markup=language_keyboard(),
            enabled=settings.telegram_use_rich_messages,
        )
        return

    if not entry.profile_completed:
        if entry.requires_onboarding_before_sales:
            from bot.routers.onboarding import send_onboarding_step

            await send_onboarding_step(
                message=message,
                db=db,
                user_id=entry.user_id,
                campaign_product_title=entry.focus_product_title,
            )
            return

        from bot.routers.sales import send_sales_pitch

        await send_sales_pitch(
            message=message,
            db=db,
            settings=settings,
            user_id=entry.user_id,
        )
        return

    if entry.product_campaign_entry:
        from bot.routers.sales import send_sales_pitch

        await send_sales_pitch(
            message=message,
            db=db,
            settings=settings,
            user_id=entry.user_id,
        )
        return

    copy = returning_prompt(entry)
    await send_rich_or_fallback(
        message.bot,
        chat_id=message.chat.id,
        markdown=copy.rich_markdown,
        fallback_text=copy.text,
        reply_markup=continue_keyboard(mini_app_url=settings.mini_app_url),
        enabled=settings.telegram_use_rich_messages,
    )
