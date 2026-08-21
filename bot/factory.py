from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.core.config import Settings
from backend.db.pool import Database
from bot.routers.fallback import router as fallback_router
from bot.routers.language import router as language_router
from bot.routers.legal import router as legal_router
from bot.routers.menu import router as menu_router
from bot.routers.onboarding import router as onboarding_router
from bot.routers.payments import router as payments_router
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


def create_dispatcher(*, db: Database, settings: Settings) -> Dispatcher:
    # Customer-critical state lives in PostgreSQL, not MemoryStorage.
    dp = Dispatcher(disable_fsm=True, db=db, settings=settings)

    # Order matters. The fallback router MUST stay last so it only receives
    # customer messages that none of the normal business flows handled.
    dp.include_routers(
        start_router,
        language_router,
        onboarding_router,
        legal_router,
        sales_router,
        payments_router,
        support_router,
        menu_router,
        fallback_router,
    )
    return dp
