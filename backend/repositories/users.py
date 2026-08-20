from __future__ import annotations

from typing import Any

import asyncpg


class UserRepository:
    async def upsert_telegram_user(
        self,
        conn: asyncpg.Connection,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None,
        telegram_language_code: str | None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, telegram_language_code,
                last_seen_at
            )
            VALUES ($1, $2, $3, $4, $5, now())
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                telegram_language_code = EXCLUDED.telegram_language_code,
                last_seen_at = now(),
                updated_at = now()
            RETURNING *
            """,
            telegram_id,
            username,
            first_name,
            last_name,
            telegram_language_code,
        )

    async def get_by_telegram_id(
        self, conn: asyncpg.Connection, telegram_id: int
    ) -> asyncpg.Record | None:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)

    async def get_by_id(self, conn: asyncpg.Connection, *, user_id: Any) -> asyncpg.Record | None:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def get_profile(
        self, conn: asyncpg.Connection, *, user_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM user_profiles WHERE user_id = $1",
            user_id,
        )

    async def set_preferred_language(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        language: str,
    ) -> asyncpg.Record:
        if language not in {"am", "en"}:
            raise ValueError("unsupported language")
        return await conn.fetchrow(
            """
            UPDATE users
            SET preferred_language = $2,
                customer_stage = CASE WHEN customer_stage = 'new' THEN 'onboarding' ELSE customer_stage END,
                updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            user_id,
            language,
        )

    async def set_customer_stage(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        stage: str,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            UPDATE users
            SET customer_stage = $2, updated_at = now()
            WHERE id = $1
            RETURNING *
            """,
            user_id,
            stage,
        )

    async def update_profile(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        preferred_language: str | None = None,
        role: str | None = None,
        ai_experience: str | None = None,
        main_goal: str | None = None,
        main_obstacle: str | None = None,
        mark_completed: bool = False,
    ) -> asyncpg.Record:
        if preferred_language is not None:
            await self.set_preferred_language(conn, user_id=user_id, language=preferred_language)

        return await conn.fetchrow(
            """
            INSERT INTO user_profiles (
                user_id, role, ai_experience, main_goal, main_obstacle, onboarding_completed_at
            )
            VALUES ($1, $2, $3, $4, $5, CASE WHEN $6 THEN now() ELSE NULL END)
            ON CONFLICT (user_id) DO UPDATE SET
                role = COALESCE(EXCLUDED.role, user_profiles.role),
                ai_experience = COALESCE(EXCLUDED.ai_experience, user_profiles.ai_experience),
                main_goal = COALESCE(EXCLUDED.main_goal, user_profiles.main_goal),
                main_obstacle = COALESCE(EXCLUDED.main_obstacle, user_profiles.main_obstacle),
                onboarding_completed_at = CASE
                    WHEN $6 THEN COALESCE(user_profiles.onboarding_completed_at, now())
                    ELSE user_profiles.onboarding_completed_at
                END,
                updated_at = now()
            RETURNING *
            """,
            user_id,
            role,
            ai_experience,
            main_goal,
            main_obstacle,
            mark_completed,
        )
