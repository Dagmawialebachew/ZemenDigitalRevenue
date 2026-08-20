from __future__ import annotations

import asyncpg

from backend.db.pool import Database


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def _connection(self) -> asyncpg.Connection:
        raise RuntimeError("Use Database.acquire()/transaction() in repository methods")
