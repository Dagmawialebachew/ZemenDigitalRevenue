from __future__ import annotations

from typing import Any

import asyncpg

from backend.domain.sales import SIGNAL_WEIGHTS, score_after_signal


class JourneyRepository:
    async def get(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT *
            FROM user_product_journeys
            WHERE user_id = $1 AND product_id = $2
            """,
            user_id,
            product_id,
        )

    async def ensure(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
        onboarding_snapshot: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO user_product_journeys (
                user_id, product_id, onboarding_snapshot, last_seen_at
            )
            VALUES ($1, $2, $3::jsonb, now())
            ON CONFLICT (user_id, product_id) DO UPDATE SET
                onboarding_snapshot = CASE
                    WHEN $3::jsonb = '{}'::jsonb
                    THEN user_product_journeys.onboarding_snapshot
                    ELSE user_product_journeys.onboarding_snapshot || $3::jsonb
                END,
                last_seen_at = now(),
                updated_at = now()
            RETURNING *
            """,
            user_id,
            product_id,
            onboarding_snapshot or {},
        )

    async def record_unique_signal(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
        signal_key: str,
        payload: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        if signal_key not in SIGNAL_WEIGHTS:
            raise ValueError(f"unsupported journey signal: {signal_key}")
        current = await self.ensure(conn, user_id=user_id, product_id=product_id)
        delta = int(SIGNAL_WEIGHTS[signal_key])
        inserted = await conn.fetchval(
            """
            INSERT INTO user_product_signals (
                user_id, product_id, signal_key, score_delta, payload
            )
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (user_id, product_id, signal_key) DO NOTHING
            RETURNING id
            """,
            user_id,
            product_id,
            signal_key,
            delta,
            payload or {},
        )
        if inserted is None:
            return await self.ensure(conn, user_id=user_id, product_id=product_id)

        target = score_after_signal(
            int(current["intent_score"]),
            signal_key,
            current_stage=str(current["stage"]),
        )
        return await conn.fetchrow(
            """
            UPDATE user_product_journeys
            SET intent_score = $3,
                stage = $4,
                last_signal_key = $5,
                last_seen_at = now(),
                buy_clicked_at = CASE
                    WHEN $5 = 'BUY_CLICKED' THEN COALESCE(buy_clicked_at, now())
                    ELSE buy_clicked_at
                END,
                updated_at = now()
            WHERE user_id = $1 AND product_id = $2
            RETURNING *
            """,
            user_id,
            product_id,
            target.score,
            target.stage,
            signal_key,
        )
