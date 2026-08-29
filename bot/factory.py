from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.error_reporting import ErrorReporter
from bot.routers.admin_campaign import router as admin_campaign_router
from bot.routers.fallback import router as fallback_router
from bot.routers.language import router as language_router
from bot.routers.legal import router as legal_router
from bot.routers.menu import router as menu_router
from bot.routers.onboarding import router as onboarding_router
from bot.routers.payments import router as payments_router
from bot.routers.retargeting import router as retargeting_router
from bot.routers.sales import router as sales_router
from bot.routers.start import router as start_router
from bot.routers.support import router as support_router
from bot.services.callbacks import ExpiredCallbackQueryMiddleware


def create_bot(settings: Settings) -> Bot:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    bot.session.middleware(ExpiredCallbackQueryMiddleware())
    return bot


def create_dispatcher(
    *, db: Database, settings: Settings, error_reporter: ErrorReporter | None = None
) -> Dispatcher:
    # Customer-critical state lives in PostgreSQL, not MemoryStorage.
    dp = Dispatcher(disable_fsm=True, db=db, settings=settings)

    async def report_unhandled_update(event: ErrorEvent, bot: Bot) -> bool:
        update = event.update
        callback = update.callback_query
        message = update.message
        user = callback.from_user if callback else message.from_user if message else None
        context: dict[str, object] = {
            "update_id": update.update_id,
            "update_kind": "callback" if callback else "message" if message else "other",
        }
        if user is not None:
            context["telegram_user_id"] = user.id
        if callback is not None:
            context["callback_data"] = callback.data or "none"
        reference = "UNAVAILABLE"
        if error_reporter is not None:
            reference = error_reporter.schedule(
                event.exception,
                surface="telegram_bot",
                context=context,
            )

        # The reporting path must never replace one failure with another.
        if user is not None:
            with suppress(Exception):
                await bot.send_message(
                    chat_id=user.id,
                    text=(
                        "⚠️ ያልተጠበቀ ችግር ተፈጥሯል። የZemen ድጋፍ ቡድን እንዲያውቅ አድርገናል።\n"
                        "እባክዎ ከጥቂት ጊዜ በኋላ ደግመው ይሞክሩ።\n\n"
                        f"Reference: <code>{reference}</code>"
                    ),
                )
        return True

    dp.errors.register(report_unhandled_update)

    # Order matters. The fallback router MUST stay last so it only receives
    # customer messages that none of the normal business flows handled.
    dp.include_routers(
        start_router,
        admin_campaign_router,
        language_router,
        onboarding_router,
        legal_router,
        sales_router,
        payments_router,
        retargeting_router,
        support_router,
        menu_router,
        fallback_router,
    )
    return dp
