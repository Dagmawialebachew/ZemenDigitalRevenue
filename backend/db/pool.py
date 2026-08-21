from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import perf_counter

import asyncpg
import orjson
import structlog

log = structlog.get_logger(__name__)


def _encode_json(value: object) -> str:
    return orjson.dumps(value).decode("utf-8")


def _decode_json(value: str) -> object:
    return orjson.loads(value)


async def _init_connection(conn: asyncpg.Connection) -> None:
    # The application passes dict/list payloads into JSONB throughout the domain.
    # Register codecs once per pooled connection so JSON values stay native Python
    # objects instead of ad-hoc json.dumps/json.loads calls scattered everywhere.
    await conn.set_type_codec(
        "json",
        schema="pg_catalog",
        encoder=_encode_json,
        decoder=_decode_json,
        format="text",
    )
    await conn.set_type_codec(
        "jsonb",
        schema="pg_catalog",
        encoder=_encode_json,
        decoder=_decode_json,
        format="text",
    )


@dataclass(slots=True)
class Database:
    dsn: str
    min_size: int = 2
    max_size: int = 10
    max_inactive_connection_lifetime: float = 300.0
    pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if not self.dsn:
            log.warning("database_disabled", reason="DATABASE_URL is empty")
            return
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            max_inactive_connection_lifetime=self.max_inactive_connection_lifetime,
            command_timeout=30,
            init=_init_connection,
        )
        log.info(
            "database_connected",
            min_size=self.min_size,
            max_size=self.max_size,
            max_inactive_connection_lifetime=self.max_inactive_connection_lifetime,
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None
            log.info("database_closed")

    def require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Database pool is not connected")
        return self.pool

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        pool = self.require_pool()
        started = perf_counter()
        async with pool.acquire() as conn:
            wait_ms = (perf_counter() - started) * 1000
            if wait_ms >= 250:
                log.warning("database_pool_slow_acquire", wait_ms=round(wait_ms, 1))
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        pool = self.require_pool()
        started = perf_counter()
        async with pool.acquire() as conn:
            wait_ms = (perf_counter() - started) * 1000
            if wait_ms >= 250:
                log.warning("database_pool_slow_acquire", wait_ms=round(wait_ms, 1))
            async with conn.transaction():
                yield conn

    async def ping(self) -> bool:
        if self.pool is None:
            return False
        async with self.pool.acquire() as conn:
            value = await conn.fetchval("SELECT 1")
        return value == 1
