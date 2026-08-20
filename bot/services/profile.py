from __future__ import annotations

from typing import Any

from backend.db.pool import Database
from backend.repositories.events import EventRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.users import UserRepository


class CustomerProfileService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository()
        self.sessions = ConversationSessionRepository()
        self.events = EventRepository()

    async def set_language(self, *, user_id: Any, language: str) -> None:
        if language not in {"am", "en"}:
            raise ValueError("unsupported language")
        async with self.db.transaction() as conn:
            await self.users.set_preferred_language(conn, user_id=user_id, language=language)
            session = await self.sessions.set_language_step(
                conn, user_id=user_id, language=language
            )
            await self.events.append(
                conn,
                event_type="LANGUAGE_SELECTED",
                user_id=user_id,
                product_id=session["focus_product_id"] if session else None,
                tracking_link_id=session["focus_tracking_link_id"] if session else None,
                payload={"language": language},
            )
