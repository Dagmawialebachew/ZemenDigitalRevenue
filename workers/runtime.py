from __future__ import annotations

from aiogram import Bot

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.error_reporting import ErrorReporter
from workers.engine import WorkerSupervisor
from workers.handlers import build_registry


def create_worker_supervisor(
    *,
    db: Database,
    settings: Settings,
    bot: Bot | None,
    error_reporter: ErrorReporter | None = None,
) -> WorkerSupervisor:
    return WorkerSupervisor(
        db=db,
        settings=settings,
        registry=build_registry(),
        bot=bot,
        error_reporter=error_reporter,
    )
