from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OpsTopics:
    group_id: int | None
    new_users: int | None = None
    payments: int | None = None
    sales: int | None = None
    support: int | None = None
    alerts: int | None = None


class OpsNotifier:
    def __init__(self, bot: Bot, topics: OpsTopics) -> None:
        self.bot = bot
        self.topics = topics

    async def send(self, *, topic_id: int | None, text: str) -> None:
        if not self.topics.group_id:
            return
        try:
            await self.bot.send_message(
                chat_id=self.topics.group_id,
                message_thread_id=topic_id,
                text=text,
            )
        except Exception:
            # Ops notification failure must never break the customer flow.
            log.exception("ops_notification_failed", topic_id=topic_id)
