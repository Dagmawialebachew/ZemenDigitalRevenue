from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from backend.api.router import api_router
from backend.core.config import get_settings
from backend.core.logging import configure_logging
from backend.middleware.control_security import ControlMutationGuardMiddleware
from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.worker_wake import WorkerWakeMiddleware
from backend.static_apps import mount_static_apps
from backend.db.pool import Database
from bot.factory import create_bot, create_dispatcher
from bot.services.setup import configure_bot_ui
from backend.services.operations import OperationsService
from backend.services.marketing import MarketingService
from shared.constants import BotMode
from workers.runtime import create_worker_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = structlog.get_logger("zemen.lifecycle")

    db = Database(
        dsn=settings.database_url,
        min_size=settings.db_min_pool_size,
        max_size=settings.db_max_pool_size,
        max_inactive_connection_lifetime=settings.db_max_inactive_connection_lifetime_seconds,
    )
    await db.connect()
    app.state.db = db
    app.state.bot = None
    app.state.dispatcher = None
    app.state.workers = None
    polling_task: asyncio.Task[None] | None = None

    errors = settings.runtime_errors()
    if errors:
        log.warning("runtime_configuration_incomplete", errors=errors)

    bot = None
    if settings.bot_token:
        if db.pool is None:
            log.error("telegram_not_started", reason="DATABASE_URL is required by S04 salesman core")
        else:
            bot = create_bot(settings)
            dispatcher = create_dispatcher(db=db, settings=settings)
            app.state.bot = bot
            app.state.dispatcher = dispatcher
            await configure_bot_ui(bot, settings)

            if settings.bot_mode == BotMode.POLLING:
                polling_task = asyncio.create_task(
                    dispatcher.start_polling(bot, handle_signals=False),
                    name="telegram-polling",
                )
                log.info("telegram_polling_started")
            elif settings.webhook_url and settings.telegram_webhook_secret:
                await bot.set_webhook(
                    settings.webhook_url,
                    secret_token=settings.telegram_webhook_secret,
                    drop_pending_updates=False,
                )
                log.info("telegram_webhook_configured", url=settings.webhook_url)

    if settings.workers_enabled and db.pool is not None:
        workers = create_worker_supervisor(db=db, settings=settings, bot=bot)
        await workers.start()
        app.state.workers = workers
        await OperationsService(db, settings).ensure_maintenance_job()
        await MarketingService(db, settings, bot).ensure_maintenance_job()

    try:
        yield
    finally:
        if app.state.workers is not None:
            await app.state.workers.stop()
        if polling_task is not None:
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task
        if app.state.bot is not None:
            await app.state.bot.session.close()
        await db.close()
        log.info("zemen_shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Zemen Digital API",
        version="1.0.0-s12",
        lifespan=lifespan,
    )
    settings = get_settings()
    allowed_origins = tuple(dict.fromkeys((*settings.mini_app_allowed_origins, *settings.control_allowed_origins)))
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(WorkerWakeMiddleware)
    app.add_middleware(ControlMutationGuardMiddleware, settings=settings)
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(allowed_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Ops-Key", "X-CSRF-Token"],
        )
    app.include_router(api_router)
    mount_static_apps(app, enabled=settings.static_apps_enabled)
    return app


app = create_app()
