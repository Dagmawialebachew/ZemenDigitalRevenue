from __future__ import annotations

from typing import Any

import asyncpg


class ReferralRepository:
    async def get_attribution_for_user(
        self, conn: asyncpg.Connection, *, referred_user_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT ra.*, u.username AS referrer_username, u.first_name AS referrer_first_name
            FROM referral_attributions ra
            JOIN users u ON u.id = ra.referrer_user_id
            WHERE ra.referred_user_id = $1 AND ra.status = 'active'
            """,
            referred_user_id,
        )

    async def create_first_touch_attribution(
        self,
        conn: asyncpg.Connection,
        *,
        referral_account_id: Any,
        referrer_user_id: Any,
        referred_user_id: Any,
        first_product_id: Any | None = None,
    ) -> asyncpg.Record | None:
        if str(referrer_user_id) == str(referred_user_id):
            return None

        row = await conn.fetchrow(
            """
            INSERT INTO referral_attributions (
                referral_account_id, referrer_user_id, referred_user_id, first_product_id
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (referred_user_id) DO NOTHING
            RETURNING *
            """,
            referral_account_id,
            referrer_user_id,
            referred_user_id,
            first_product_id,
        )
        if row is not None:
            return row
        return await conn.fetchrow(
            "SELECT * FROM referral_attributions WHERE referred_user_id = $1",
            referred_user_id,
        )
