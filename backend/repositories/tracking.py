from __future__ import annotations

from typing import Any

import asyncpg


class TrackingRepository:
    async def resolve_source_token(
        self, conn: asyncpg.Connection, token: str
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT *
            FROM tracking_links
            WHERE token = $1 AND is_active = TRUE
            """,
            token,
        )

    async def get_by_id(
        self, conn: asyncpg.Connection, tracking_link_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM tracking_links WHERE id = $1",
            tracking_link_id,
        )

    async def record_source_touch(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        tracking_link_id: Any | None,
        raw_start_payload: str,
        touch_type: str,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO user_sources (user_id, tracking_link_id, raw_start_payload, touch_type)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            user_id,
            tracking_link_id,
            raw_start_payload,
            touch_type,
        )

    async def resolve_referral_code(
        self, conn: asyncpg.Connection, code: str
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT ra.*, u.telegram_id AS owner_telegram_id
            FROM referral_accounts ra
            JOIN users u ON u.id = ra.owner_user_id
            WHERE ra.code = $1 AND ra.is_active = TRUE
            """,
            code,
        )
