from __future__ import annotations

from backend.db.pool import Database


class SourceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def resolve_source_token(self, token: str):
        sql = """
        SELECT sl.*, p.public_id AS product_public_id
        FROM source_links sl
        LEFT JOIN products p ON p.id = sl.product_id
        WHERE sl.token=$1 AND sl.is_active=TRUE
        """
        async with self.db.acquire() as conn:
            return await conn.fetchrow(sql, token)

    async def attach_source_once(self, user_id: int, source_link_id: int) -> None:
        sql = """
        INSERT INTO user_sources (user_id, source_link_id, first_touch, last_touch)
        VALUES ($1, $2, TRUE, TRUE)
        ON CONFLICT (user_id, source_link_id) DO UPDATE SET
            last_touch=TRUE, last_seen_at=now()
        """
        async with self.db.transaction() as conn:
            await conn.execute("UPDATE user_sources SET last_touch=FALSE WHERE user_id=$1", user_id)
            await conn.execute(sql, user_id, source_link_id)
