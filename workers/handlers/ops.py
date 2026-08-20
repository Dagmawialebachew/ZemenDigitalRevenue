from __future__ import annotations

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)

from workers.context import WorkerContext
from workers.errors import PermanentJobError, RetryableJobError
from workers.models import Job

_TOPIC_SETTING = {
    "new_users": "zemen_ops_topic_new_users",
    "payments": "zemen_ops_topic_payments",
    "sales": "zemen_ops_topic_sales",
    "support": "zemen_ops_topic_support",
    "alerts": "zemen_ops_topic_alerts",
}


async def notify_ops_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot is unavailable", code="BOT_UNAVAILABLE")

    group_id = ctx.settings.zemen_ops_group_id
    if not group_id:
        raise PermanentJobError("ZEMEN_OPS_GROUP_ID is not configured", code="OPS_NOT_CONFIGURED")

    topic = str(job.payload.get("topic", "alerts"))
    if topic not in _TOPIC_SETTING:
        raise PermanentJobError(f"Unknown ZEMEN OPS topic: {topic}", code="BAD_OPS_TOPIC")

    text = str(job.payload.get("text", "")).strip()
    if not text:
        raise PermanentJobError("OPS notification text is empty", code="BAD_PAYLOAD")

    topic_id = getattr(ctx.settings, _TOPIC_SETTING[topic])
    disable_notification = bool(job.payload.get("disable_notification", False))

    try:
        message = await ctx.bot.send_message(
            chat_id=group_id,
            message_thread_id=topic_id,
            text=text,
            disable_notification=disable_notification,
        )
    except TelegramRetryAfter as exc:
        raise RetryableJobError(
            "Telegram flood control",
            retry_after=float(exc.retry_after),
            code="TELEGRAM_RETRY_AFTER",
        ) from exc
    except (TelegramNetworkError, TelegramServerError) as exc:
        raise RetryableJobError(str(exc), code="TELEGRAM_TRANSIENT") from exc
    except (TelegramBadRequest, TelegramNotFound, TelegramForbiddenError) as exc:
        raise PermanentJobError(str(exc), code="TELEGRAM_DESTINATION_ERROR") from exc
    except TelegramUnauthorizedError as exc:
        raise PermanentJobError(str(exc), code="TELEGRAM_AUTH_ERROR") from exc

    return {"message_id": message.message_id, "topic": topic}
