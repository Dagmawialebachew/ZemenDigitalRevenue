from __future__ import annotations

from typing import Any, Iterable

import asyncpg


class SalesContentRepository:
    async def get_best_block(
        self,
        conn: asyncpg.Connection,
        *,
        product_id: Any,
        language: str,
        block_key: str,
        audience_keys: Iterable[str],
    ) -> asyncpg.Record | None:
        keys = list(dict.fromkeys(audience_keys)) or ["default"]
        return await conn.fetchrow(
            """
            SELECT *
            FROM product_content_blocks
            WHERE product_id = $1
              AND language = $2
              AND block_key = $3
              AND is_active = TRUE
              AND audience_key = ANY($4::text[])
            ORDER BY array_position($4::text[], audience_key), version DESC
            LIMIT 1
            """,
            product_id,
            language,
            block_key,
            keys,
        )
