from __future__ import annotations

from aiogram.types import User as TelegramUser

from backend.db.pool import Database
from backend.services.customer_entry import CustomerEntryContext
from shared.deeplinks import StartKind


async def load_current_entry_context(
    db: Database,
    *,
    telegram_user: TelegramUser,
) -> CustomerEntryContext | None:
    async with db.acquire() as conn:
        current = await conn.fetchrow(
            """
            SELECT
                u.id AS user_id,
                u.telegram_id,
                u.first_name,
                u.username,
                u.preferred_language,
                u.customer_stage,
                (up.onboarding_completed_at IS NOT NULL) AS profile_completed,
                cs.last_start_kind,
                cs.focus_product_id,
                COALESCE(pt.title, fallback.title, p.slug) AS focus_product_title,
                p.regular_price_br AS focus_product_price_br
            FROM users u
            LEFT JOIN user_profiles up ON up.user_id = u.id
            LEFT JOIN conversation_sessions cs ON cs.user_id = u.id
            LEFT JOIN products p
                ON p.id = cs.focus_product_id
               AND p.status = 'active'
            LEFT JOIN product_translations pt
                ON pt.product_id = p.id
               AND pt.language = COALESCE(u.preferred_language, 'am')
            LEFT JOIN product_translations fallback
                ON fallback.product_id = p.id
               AND fallback.language = p.default_language
            WHERE u.telegram_id = $1
            """,
            telegram_user.id,
        )
        if current is None:
            return None
        try:
            start_kind = StartKind(current["last_start_kind"] or StartKind.EMPTY)
        except ValueError:
            start_kind = StartKind.UNKNOWN
        return CustomerEntryContext(
            user_id=current["user_id"],
            telegram_id=current["telegram_id"],
            first_name=current["first_name"],
            username=current["username"],
            is_new_user=False,
            preferred_language=current["preferred_language"],
            profile_completed=bool(current["profile_completed"]),
            customer_stage=current["customer_stage"],
            start_kind=start_kind,
            start_token=None,
            focus_product_id=current["focus_product_id"],
            focus_product_title=current["focus_product_title"],
            focus_product_price_br=(
                str(current["focus_product_price_br"])
                if current["focus_product_price_br"] is not None
                else None
            ),
        )
