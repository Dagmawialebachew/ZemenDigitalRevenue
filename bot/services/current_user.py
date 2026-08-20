from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogram.types import User as TelegramUser

from backend.db.pool import Database
from backend.repositories.products import ProductRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.users import UserRepository
from backend.services.customer_entry import CustomerEntryContext
from shared.deeplinks import StartKind


async def load_current_entry_context(
    db: Database,
    *,
    telegram_user: TelegramUser,
) -> CustomerEntryContext | None:
    users = UserRepository()
    sessions = ConversationSessionRepository()
    products = ProductRepository()
    async with db.acquire() as conn:
        user = await users.get_by_telegram_id(conn, telegram_user.id)
        if user is None:
            return None
        profile = await users.get_profile(conn, user_id=user["id"])
        session = await sessions.get(conn, user_id=user["id"])
        product_card = None
        if session and session["focus_product_id"]:
            product_card = await products.get_sales_card(
                conn,
                product_id=session["focus_product_id"],
                language=user["preferred_language"] or "am",
            )
        try:
            start_kind = StartKind(session["last_start_kind"]) if session else StartKind.EMPTY
        except ValueError:
            start_kind = StartKind.UNKNOWN
        return CustomerEntryContext(
            user_id=user["id"],
            telegram_id=user["telegram_id"],
            first_name=user["first_name"],
            username=user["username"],
            is_new_user=False,
            preferred_language=user["preferred_language"],
            profile_completed=bool(profile and profile["onboarding_completed_at"]),
            customer_stage=user["customer_stage"],
            start_kind=start_kind,
            start_token=None,
            focus_product_id=session["focus_product_id"] if session else None,
            focus_product_title=product_card["title"] if product_card else None,
            focus_product_price_br=(str(product_card["regular_price_br"]) if product_card else None),
        )
