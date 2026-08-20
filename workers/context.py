from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.jobs import JobRepository


@dataclass(slots=True)
class WorkerContext:
    settings: Settings
    db: Database
    jobs: JobRepository
    bot: Bot | None
