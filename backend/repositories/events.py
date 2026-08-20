from __future__ import annotations

from typing import Any

import asyncpg


class EventRepository:
    async def append(
        self,
        conn: asyncpg.Connection,
        *,
        event_type: str,
        user_id: Any | None = None,
        product_id: Any | None = None,
        order_id: Any | None = None,
        tracking_link_id: Any | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        return await conn.fetchval(
            """
            INSERT INTO events (
                event_type, user_id, product_id, order_id, tracking_link_id, payload
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id
            """,
            event_type,
            user_id,
            product_id,
            order_id,
            tracking_link_id,
            payload or {},
        )
