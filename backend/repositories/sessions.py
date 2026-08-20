from __future__ import annotations

from typing import Any

import asyncpg


class ConversationSessionRepository:
    async def get(self, conn: asyncpg.Connection, *, user_id: Any) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM conversation_sessions WHERE user_id = $1",
            user_id,
        )

    async def upsert(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        active_flow: str = "entry",
        step_key: str = "start",
        focus_product_id: Any | None = None,
        focus_tracking_link_id: Any | None = None,
        referral_attribution_id: Any | None = None,
        last_start_kind: str = "empty",
        last_start_payload: str = "",
        context: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO conversation_sessions (
                user_id, active_flow, step_key, focus_product_id,
                focus_tracking_link_id, referral_attribution_id,
                last_start_kind, last_start_payload, context
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
            ON CONFLICT (user_id) DO UPDATE SET
                active_flow = EXCLUDED.active_flow,
                step_key = EXCLUDED.step_key,
                focus_product_id = COALESCE(EXCLUDED.focus_product_id, conversation_sessions.focus_product_id),
                focus_tracking_link_id = COALESCE(EXCLUDED.focus_tracking_link_id, conversation_sessions.focus_tracking_link_id),
                referral_attribution_id = COALESCE(EXCLUDED.referral_attribution_id, conversation_sessions.referral_attribution_id),
                last_start_kind = EXCLUDED.last_start_kind,
                last_start_payload = EXCLUDED.last_start_payload,
                context = conversation_sessions.context || EXCLUDED.context,
                last_interaction_at = now(),
                updated_at = now()
            RETURNING *
            """,
            user_id,
            active_flow,
            step_key,
            focus_product_id,
            focus_tracking_link_id,
            referral_attribution_id,
            last_start_kind,
            last_start_payload,
            context or {},
        )

    async def set_language_step(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        language: str,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            UPDATE conversation_sessions
            SET active_flow = 'onboarding',
                step_key = 'profile_role',
                context = context || jsonb_build_object('language', $2::text),
                last_interaction_at = now(),
                updated_at = now()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            language,
        )

    async def set_onboarding_step(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        step_key: str,
        context_patch: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            UPDATE conversation_sessions
            SET active_flow = 'onboarding',
                step_key = $2,
                context = context || $3::jsonb,
                last_interaction_at = now(),
                updated_at = now()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            step_key,
            context_patch or {},
        )

    async def complete_onboarding(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            UPDATE conversation_sessions
            SET active_flow = 'sales',
                step_key = 'sales_intro',
                context = context || jsonb_build_object('onboarding_completed', true),
                last_interaction_at = now(),
                updated_at = now()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
        )

    async def set_sales_step(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        step_key: str,
        context_patch: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            UPDATE conversation_sessions
            SET active_flow = 'sales',
                step_key = $2,
                context = context || $3::jsonb,
                last_interaction_at = now(),
                updated_at = now()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            step_key,
            context_patch or {},
        )

    async def touch(self, conn: asyncpg.Connection, *, user_id: Any) -> None:
        await conn.execute(
            """
            UPDATE conversation_sessions
            SET last_interaction_at = now(), updated_at = now()
            WHERE user_id = $1
            """,
            user_id,
        )

    async def set_focus_product(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            UPDATE conversation_sessions
            SET focus_product_id = $2,
                active_flow = 'sales',
                step_key = 'sales_intro',
                last_interaction_at = now(),
                updated_at = now()
            WHERE user_id = $1
            RETURNING *
            """,
            user_id,
            product_id,
        )