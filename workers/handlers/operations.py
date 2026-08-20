from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter, TelegramServerError

from backend.repositories.operations import OperationsRepository
from backend.services.operations import OperationsService
from bot.keyboards.support import support_ops_keyboard
from workers.context import WorkerContext
from workers.errors import PermanentJobError, RetryableJobError
from workers.models import Job


def _map_telegram(exc: Exception) -> Exception:
    if isinstance(exc, TelegramRetryAfter):
        return RetryableJobError("Telegram flood control", retry_after=float(exc.retry_after), code="TELEGRAM_RETRY_AFTER")
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        return RetryableJobError(str(exc), code="TELEGRAM_TRANSIENT")
    if isinstance(exc, (TelegramBadRequest, TelegramForbiddenError)):
        return PermanentJobError(str(exc), code="TELEGRAM_DESTINATION_ERROR")
    return exc


async def maintenance_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    return await OperationsService(ctx.db, ctx.settings).maintenance_tick(current_job_id=job.id)


async def ops_alert_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot unavailable", code="BOT_UNAVAILABLE")
    try:
        alert_id = UUID(str(job.payload.get("alert_id", "")))
    except ValueError as exc:
        raise PermanentJobError("Invalid alert id", code="BAD_PAYLOAD") from exc
    repo = OperationsRepository()
    async with ctx.db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM operational_alerts WHERE id=$1", alert_id)
    if row is None:
        raise PermanentJobError("Alert not found", code="ALERT_NOT_FOUND")
    if row["ops_message_id"]:
        return {"deduped": True, "message_id": int(row["ops_message_id"])}
    group = ctx.settings.zemen_ops_group_id
    if not group:
        raise PermanentJobError("ZEMEN_OPS_GROUP_ID not configured", code="OPS_NOT_CONFIGURED")
    icon = "🚨" if row["severity"] == "critical" else "⚠️" if row["severity"] == "warning" else "ℹ️"
    text = (
        f"{icon} <b>{escape(row['title'])}</b>\n\n"
        f"{escape(row['body'] or '')}\n\n"
        f"Type: <code>{escape(row['alert_type'])}</code>"
    )
    try:
        msg = await ctx.bot.send_message(
            chat_id=group,
            message_thread_id=ctx.settings.zemen_ops_topic_alerts,
            text=text,
        )
    except Exception as exc:
        mapped = _map_telegram(exc)
        if mapped is not exc:
            raise mapped from exc
        raise
    async with ctx.db.transaction() as conn:
        await repo.record_alert_message(conn, alert_id=alert_id, chat_id=int(group), message_id=msg.message_id)
    return {"message_id": msg.message_id}


async def support_case_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot unavailable", code="BOT_UNAVAILABLE")
    case_public_id = str(job.payload.get("case_public_id", ""))
    support_message_id = int(job.payload.get("support_message_id", 0) or 0)
    repo = OperationsRepository()
    async with ctx.db.acquire() as conn:
        case = await repo.support_context(conn, case_public_id=case_public_id)
        sm = await conn.fetchrow("SELECT * FROM support_messages WHERE id=$1", support_message_id)
        existing = await conn.fetchrow(
            "SELECT * FROM support_ops_messages WHERE support_message_id=$1 LIMIT 1", support_message_id
        )
    if case is None or sm is None:
        raise PermanentJobError("Support context not found", code="SUPPORT_NOT_FOUND")
    if existing is not None:
        return {"deduped": True, "message_id": int(existing["ops_message_id"])}
    group = ctx.settings.zemen_ops_group_id
    if not group:
        raise PermanentJobError("ZEMEN_OPS_GROUP_ID not configured", code="OPS_NOT_CONFIGURED")
    username = f"@{escape(case['username'])}" if case["username"] else "No username"
    text = (
        f"💬 <b>SUPPORT · {escape(case_public_id)}</b>\n\n"
        f"👤 {escape(case['first_name'] or 'Customer')} · {username}\n"
        f"🆔 <code>{case['telegram_id']}</code>\n\n"
        f"{escape(sm['body'] or '[attachment]')}\n\n"
        f"<code>CASE:{escape(case_public_id)}</code>"
    )
    attachment = dict(sm["attachment"] or {}) if sm["attachment"] else {}
    try:
        if attachment.get("type") == "photo":
            msg = await ctx.bot.send_photo(
                chat_id=group,
                message_thread_id=ctx.settings.zemen_ops_topic_support,
                photo=attachment["telegram_file_id"],
                caption=text[:1024],
                reply_markup=support_ops_keyboard(case_public_id=case_public_id),
            )
        elif attachment.get("type") == "document":
            msg = await ctx.bot.send_document(
                chat_id=group,
                message_thread_id=ctx.settings.zemen_ops_topic_support,
                document=attachment["telegram_file_id"],
                caption=text[:1024],
                reply_markup=support_ops_keyboard(case_public_id=case_public_id),
            )
        else:
            msg = await ctx.bot.send_message(
                chat_id=group,
                message_thread_id=ctx.settings.zemen_ops_topic_support,
                text=text,
                reply_markup=support_ops_keyboard(case_public_id=case_public_id),
            )
    except Exception as exc:
        mapped = _map_telegram(exc)
        if mapped is not exc:
            raise mapped from exc
        raise
    async with ctx.db.transaction() as conn:
        await repo.record_support_ops_message(
            conn,
            case_id=case["id"],
            support_message_id=support_message_id,
            chat_id=int(group),
            thread_id=ctx.settings.zemen_ops_topic_support,
            message_id=msg.message_id,
        )
    return {"case_public_id": case_public_id, "message_id": msg.message_id}
