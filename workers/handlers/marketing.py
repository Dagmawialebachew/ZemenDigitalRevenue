from __future__ import annotations

import secrets
from typing import Any
from html import escape
from uuid import UUID

from aiogram.enums import ButtonStyle
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter, TelegramServerError
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.repositories.events import EventRepository
from backend.repositories.marketing import MarketingRepository
from backend.services.marketing import MarketingService
from bot.keyboards.primitives import inline_action
from workers.context import WorkerContext
from workers.errors import PermanentJobError, RetryableJobError
from workers.models import EnqueueJob, Job


def _telegram_error(exc: Exception) -> Exception:
    if isinstance(exc, TelegramRetryAfter):
        return RetryableJobError("Telegram flood control", retry_after=float(exc.retry_after), code="TELEGRAM_RETRY_AFTER")
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        return RetryableJobError(str(exc), code="TELEGRAM_TRANSIENT")
    if isinstance(exc, (TelegramBadRequest, TelegramForbiddenError)):
        return PermanentJobError(str(exc), code="TELEGRAM_DESTINATION_ERROR")
    return exc


async def automation_trigger_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    try:
        automation_id = UUID(str(job.payload.get("automation_id", "")))
        event_id = int(job.payload.get("event_id", 0))
    except (ValueError, TypeError) as exc:
        raise PermanentJobError("Invalid automation trigger payload", code="BAD_PAYLOAD") from exc
    return await MarketingService(ctx.db, ctx.settings, ctx.bot).trigger_automation_from_event(automation_id=automation_id, event_id=event_id)


async def automation_step_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    try:
        run_id = UUID(str(job.payload.get("run_id", "")))
    except ValueError as exc:
        raise PermanentJobError("Invalid automation run id", code="BAD_PAYLOAD") from exc
    step_key = str(job.payload.get("step_key", ""))
    if not step_key:
        raise PermanentJobError("Missing automation step key", code="BAD_PAYLOAD")
    return await MarketingService(ctx.db, ctx.settings, ctx.bot).execute_automation_step(run_id=run_id, step_key=step_key)


async def automation_message_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot unavailable", code="BOT_UNAVAILABLE")
    try:
        run_id = UUID(str(job.payload.get("run_id", "")))
    except ValueError as exc:
        raise PermanentJobError("Invalid automation run id", code="BAD_PAYLOAD") from exc
    step_key = str(job.payload.get("step_key", ""))
    async with ctx.db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.id,r.user_id,r.product_id,r.status,u.telegram_id,COALESCE(u.preferred_language,'am') AS language,
                   s.config,COALESCE(am.title,en.title,p.slug) AS product_title,
                   EXISTS(SELECT 1 FROM customer_offers co WHERE co.automation_run_id=r.id AND co.status='available' AND (co.expires_at IS NULL OR co.expires_at>now())) AS has_offer
            FROM automation_runs r JOIN users u ON u.id=r.user_id
            JOIN automation_steps s ON s.automation_id=r.automation_id AND s.step_key=$2
            LEFT JOIN products p ON p.id=r.product_id
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            WHERE r.id=$1
            """,
            run_id, step_key,
        )
    if row is None:
        raise PermanentJobError("Automation message context not found", code="AUTOMATION_CONTEXT_MISSING")
    config = dict(row["config"] or {})
    lang = "en" if row["language"] == "en" else "am"
    text = str(config.get(lang) or config.get("am") or config.get("en") or "").strip()
    if not text:
        return {"skipped": True, "reason": "no_localized_copy"}
    builder = InlineKeyboardBuilder()
    label = str(config.get(f"button_text_{lang}") or "").strip()
    if label:
        builder.row(inline_action(
            text=label,
            callback_data="sales:buy" if row["has_offer"] else "sales:continue",
            style=ButtonStyle.SUCCESS,
        ))
    markup = builder.as_markup() if label else None
    try:
        msg = await ctx.bot.send_message(chat_id=int(row["telegram_id"]), text=text, reply_markup=markup)
    except TelegramForbiddenError:
        async with ctx.db.transaction() as conn:
            await conn.execute("UPDATE users SET is_bot_blocked=TRUE,updated_at=now() WHERE id=$1", row["user_id"])
            await conn.execute(
                "UPDATE automation_runs SET status='stopped',stop_reason='bot_blocked',completed_at=now(),next_run_at=NULL,updated_at=now() WHERE id=$1 AND status IN ('active','waiting')",
                run_id,
            )
        return {"blocked": True}
    except Exception as exc:
        mapped = _telegram_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise
    async with ctx.db.transaction() as conn:
        await EventRepository().append(
            conn, event_type="AUTOMATION_MESSAGE_SENT", user_id=row["user_id"], product_id=row["product_id"],
            payload={"automation_run_id": str(run_id), "step_key": step_key, "telegram_message_id": msg.message_id},
        )
    return {"message_id": msg.message_id, "telegram_id": int(row["telegram_id"])}


async def offer_expire_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    try:
        offer_id = UUID(str(job.payload.get("offer_id", "")))
    except ValueError as exc:
        raise PermanentJobError("Invalid offer id", code="BAD_PAYLOAD") from exc
    return await MarketingService(ctx.db, ctx.settings, ctx.bot).expire_offer(offer_id=offer_id)


async def marketing_maintenance_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    return await MarketingService(ctx.db, ctx.settings, ctx.bot).maintenance_tick()


async def _finalize_broadcast_if_terminal(conn: Any, broadcast_id: UUID) -> bool:
    """Complete a broadcast only when no recipient is still waiting on a send job."""
    row = await conn.fetchrow(
        """
        SELECT b.status,
               count(*) FILTER (WHERE br.status='queued') AS queued,
               count(*) FILTER (WHERE br.status='sent') AS sent,
               count(*) FILTER (WHERE br.status='failed') AS failed,
               count(*) FILTER (WHERE br.status='blocked') AS blocked,
               count(*) FILTER (WHERE br.status='skipped') AS skipped
        FROM broadcasts b
        LEFT JOIN broadcast_recipients br ON br.broadcast_id=b.id
        WHERE b.id=$1
        GROUP BY b.status
        """,
        broadcast_id,
    )
    if row is None or row["status"] in {"sent", "cancelled", "failed"}:
        return False
    if int(row["queued"] or 0) > 0:
        return False
    await conn.execute(
        "UPDATE broadcasts SET status='sent',completed_at=COALESCE(completed_at,now()),updated_at=now() WHERE id=$1 AND status IN ('scheduled','sending')",
        broadcast_id,
    )
    return True


async def broadcast_dispatch_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    try:
        broadcast_id = UUID(str(job.payload.get("broadcast_id", "")))
        revision = int(job.payload.get("revision", 0))
        batch_no = int(job.payload.get("batch_no", 1))
    except (ValueError, TypeError) as exc:
        raise PermanentJobError("Invalid broadcast dispatch payload", code="BAD_PAYLOAD") from exc
    async with ctx.db.transaction() as conn:
        b = await conn.fetchrow("SELECT * FROM broadcasts WHERE id=$1 FOR UPDATE", broadcast_id)
        if b is None:
            raise PermanentJobError("Broadcast not found", code="BROADCAST_NOT_FOUND")
        if b["status"] in {"cancelled", "sent"} or int(b["revision"]) != revision:
            return {"stale": True, "status": b["status"]}
        if b["status"] == "scheduled":
            await conn.execute("UPDATE broadcasts SET status='sending',started_at=COALESCE(started_at,now()),updated_at=now() WHERE id=$1", broadcast_id)
        recipients = await conn.fetch(
            """SELECT user_id FROM broadcast_recipients WHERE broadcast_id=$1 AND status='queued' AND last_job_id IS NULL ORDER BY user_id LIMIT $2 FOR UPDATE SKIP LOCKED""",
            broadcast_id, ctx.settings.broadcast_dispatch_batch_size,
        )
        for r in recipients:
            child = await ctx.jobs.enqueue_in_tx(conn, EnqueueJob(
                job_type="marketing.broadcast.send", queue="broadcast",
                job_key=f"broadcast:send:{broadcast_id}:{r['user_id']}",
                payload={"broadcast_id": str(broadcast_id), "user_id": str(r["user_id"])},
                priority=70, max_attempts=ctx.settings.broadcast_send_max_attempts,
            ))
            await conn.execute("UPDATE broadcast_recipients SET last_job_id=$3,updated_at=now() WHERE broadcast_id=$1 AND user_id=$2", broadcast_id, r["user_id"], child.id)
        remaining = int(await conn.fetchval(
            "SELECT count(*) FROM broadcast_recipients WHERE broadcast_id=$1 AND status='queued' AND last_job_id IS NULL",
            broadcast_id,
        ) or 0)
        if remaining:
            next_batch = batch_no + 1
            await ctx.jobs.enqueue_in_tx(conn, EnqueueJob(
                job_type="marketing.broadcast.dispatch", queue="broadcast",
                job_key=f"broadcast:dispatch:{broadcast_id}:r{revision}:batch:{next_batch}",
                payload={"broadcast_id": str(broadcast_id), "batch_no": next_batch, "revision": revision},
                priority=60, max_attempts=8,
            ))
        else:
            await _finalize_broadcast_if_terminal(conn, broadcast_id)
    return {"queued": len(recipients), "remaining": remaining, "batch": batch_no}


def _markup(buttons: list[dict[str, str]], public_base: str) -> tuple[InlineKeyboardMarkup | None, list[tuple[str, str]]]:
    if not buttons:
        return None, []
    builder = InlineKeyboardBuilder(); created=[]
    for i,b in enumerate(buttons):
        token=b["token"]
        tracked=f"{public_base.rstrip('/')}/api/public/m/{token}" if public_base else b["url"]
        builder.row(inline_action(text=b["text"],url=tracked,style=ButtonStyle.SUCCESS if i==0 else ButtonStyle.PRIMARY))
        created.append((b["key"],tracked))
    return builder.as_markup(),created


async def broadcast_send_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot unavailable", code="BOT_UNAVAILABLE")
    try:
        broadcast_id=UUID(str(job.payload.get("broadcast_id",""))); user_id=UUID(str(job.payload.get("user_id","")))
    except ValueError as exc:
        raise PermanentJobError("Invalid broadcast send payload", code="BAD_PAYLOAD") from exc
    async with ctx.db.transaction() as conn:
        row=await conn.fetchrow(
            """SELECT br.*,b.status AS broadcast_status,b.content_am,b.content_en,u.telegram_id,u.is_bot_blocked,COALESCE(u.preferred_language,'am') AS preferred_language
               FROM broadcast_recipients br JOIN broadcasts b ON b.id=br.broadcast_id JOIN users u ON u.id=br.user_id
               WHERE br.broadcast_id=$1 AND br.user_id=$2 FOR UPDATE OF br""",
            broadcast_id,user_id,
        )
        if row is None: raise PermanentJobError("Broadcast recipient not found",code="RECIPIENT_NOT_FOUND")
        if row["status"] != "queued": return {"deduped":True,"status":row["status"]}
        if row["broadcast_status"] == "cancelled" or row["is_bot_blocked"]:
            status="blocked" if row["is_bot_blocked"] else "skipped"
            await conn.execute("UPDATE broadcast_recipients SET status=$3,updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",broadcast_id,user_id,status)
            await _finalize_broadcast_if_terminal(conn, broadcast_id)
            return {"skipped":True,"status":status}
        lang="en" if row["preferred_language"]=="en" else "am"
        content=dict((row["content_en"] if lang=="en" else row["content_am"]) or row["content_am"] or row["content_en"] or {})
        buttons=[]
        for b in list(content.get("buttons") or []):
            existing=await conn.fetchrow("SELECT * FROM broadcast_click_links WHERE broadcast_id=$1 AND user_id=$2 AND button_key=$3",broadcast_id,user_id,b["key"])
            if existing is None:
                for _ in range(8):
                    token=secrets.token_urlsafe(9).replace("-","_")[:18]
                    try:
                        existing=await conn.fetchrow(
                            """INSERT INTO broadcast_click_links(token,broadcast_id,user_id,button_key,destination_url) VALUES($1,$2,$3,$4,$5) RETURNING *""",
                            token,broadcast_id,user_id,b["key"],b["url"],
                        ); break
                    except Exception as exc:
                        if "duplicate" not in str(exc).lower(): raise
                if existing is None: raise RuntimeError("Could not allocate broadcast click token")
            buttons.append({"key":b["key"],"text":b["text"],"url":b["url"],"token":existing["token"]})
    markup,_=_markup(buttons,ctx.settings.public_api_base_url)
    text=str(content.get("text") or "").strip(); media=content.get("media") if isinstance(content.get("media"),dict) else None
    try:
        if media and media.get("type")=="photo": msg=await ctx.bot.send_photo(chat_id=int(row["telegram_id"]),photo=media["file_id"],caption=text or None,reply_markup=markup)
        elif media and media.get("type")=="video": msg=await ctx.bot.send_video(chat_id=int(row["telegram_id"]),video=media["file_id"],caption=text or None,reply_markup=markup)
        elif media and media.get("type")=="document": msg=await ctx.bot.send_document(chat_id=int(row["telegram_id"]),document=media["file_id"],caption=text or None,reply_markup=markup)
        else: msg=await ctx.bot.send_message(chat_id=int(row["telegram_id"]),text=text,reply_markup=markup)
    except TelegramForbiddenError:
        async with ctx.db.transaction() as conn:
            await conn.execute("UPDATE users SET is_bot_blocked=TRUE,updated_at=now() WHERE id=$1",user_id)
            await conn.execute("UPDATE broadcast_recipients SET status='blocked',attempts=attempts+1,last_error='bot blocked',updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",broadcast_id,user_id)
            await _finalize_broadcast_if_terminal(conn, broadcast_id)
        return {"blocked":True}
    except (TelegramBadRequest,) as exc:
        async with ctx.db.transaction() as conn:
            await conn.execute("UPDATE broadcast_recipients SET status='failed',attempts=attempts+1,last_error=$3,updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",broadcast_id,user_id,str(exc)[:1000])
            await _finalize_broadcast_if_terminal(conn, broadcast_id)
        return {"failed":True,"error":str(exc)}
    except Exception as exc:
        mapped=_telegram_error(exc)
        if job.final_attempt:
            async with ctx.db.transaction() as conn:
                await conn.execute("UPDATE broadcast_recipients SET status='failed',attempts=attempts+1,last_error=$3,updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",broadcast_id,user_id,str(exc)[:1000])
                await _finalize_broadcast_if_terminal(conn, broadcast_id)
            return {"failed":True,"error":str(exc)}
        if mapped is not exc: raise mapped from exc
        raise
    async with ctx.db.transaction() as conn:
        await conn.execute("UPDATE broadcast_recipients SET status='sent',attempts=attempts+1,sent_at=now(),telegram_message_id=$3,last_error=NULL,updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",broadcast_id,user_id,msg.message_id)
        await EventRepository().append(conn,event_type="BROADCAST_SENT",user_id=user_id,payload={"broadcast_id":str(broadcast_id),"telegram_message_id":msg.message_id})
        await _finalize_broadcast_if_terminal(conn, broadcast_id)
    return {"sent":True,"message_id":msg.message_id}
