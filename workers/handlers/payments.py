from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)

from backend.repositories.events import EventRepository
from backend.repositories.operations import OperationsRepository
from backend.repositories.payments import PaymentRepository
from bot.keyboards.payments import payment_followup_keyboard, payment_review_keyboard
from workers.context import WorkerContext
from workers.errors import PermanentJobError, RetryableJobError
from workers.models import Job


def _telegram_error(exc: Exception) -> Exception:
    if isinstance(exc, TelegramRetryAfter):
        return RetryableJobError(
            "Telegram flood control",
            retry_after=float(exc.retry_after),
            code="TELEGRAM_RETRY_AFTER",
        )
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        return RetryableJobError(str(exc), code="TELEGRAM_TRANSIENT")
    if isinstance(exc, (TelegramBadRequest, TelegramNotFound, TelegramForbiddenError)):
        return PermanentJobError(str(exc), code="TELEGRAM_DESTINATION_ERROR")
    if isinstance(exc, TelegramUnauthorizedError):
        return PermanentJobError(str(exc), code="TELEGRAM_AUTH_ERROR")
    return exc


def _review_caption(row: object) -> str:
    r = row
    username = f"@{escape(r['username'])}" if r["username"] else "No username"
    duplicate = dict(r["verifier_data"] or {}).get("duplicate_signal")
    referral = f"@{escape(r['referrer_username'])}" if r["referrer_username"] else "None"
    commission = (
        f"{r['referral_rate_percent_snapshot']}% if approved"
        if r["commissionable"] and r["referrer_user_id"]
        else "0 Br / not eligible"
    )
    warning = "\n⚠️ <b>DUPLICATE RECEIPT SIGNAL</b>" if duplicate else ""
    return (
        "💳 <b>NEW PAYMENT</b>\n\n"
        f"👤 <b>{escape(r['first_name'] or 'Customer')}</b> · {username}\n"
        f"🆔 <code>{r['telegram_id']}</code>\n"
        f"📦 {escape(r['product_title'])}\n"
        f"💰 Expected: <b>{r['expected_amount_br']} Br</b>\n"
        f"🏦 {escape(str(r['payment_method']).upper())}\n"
        f"🏷 {escape(str(r['pricing_type']))}\n"
        f"🤝 Referral: {referral}\n"
        f"💵 Commission: {escape(commission)}\n"
        f"🧾 <code>{escape(r['order_public_id'])}</code> · <code>{escape(r['payment_public_id'])}</code>"
        f"{warning}"
    )[:1024]


async def payment_review_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot is unavailable", code="BOT_UNAVAILABLE")
    group_id = ctx.settings.zemen_ops_group_id
    if not group_id:
        raise PermanentJobError("ZEMEN_OPS_GROUP_ID is not configured", code="OPS_NOT_CONFIGURED")
    payment_id_raw = str(job.payload.get("payment_id", ""))
    proof_id_raw = str(job.payload.get("proof_id", ""))
    try:
        payment_id = UUID(payment_id_raw)
        proof_id = UUID(proof_id_raw)
    except ValueError as exc:
        raise PermanentJobError("Invalid payment/proof id", code="BAD_PAYLOAD") from exc

    repo = PaymentRepository()
    async with ctx.db.acquire() as conn:
        row = await repo.review_context(conn, payment_id=payment_id, proof_id=proof_id)
        existing = await conn.fetchrow(
            "SELECT * FROM payment_review_messages WHERE proof_id=$1 ORDER BY created_at DESC LIMIT 1",
            proof_id,
        )
    if row is None:
        raise PermanentJobError("Payment review context not found", code="PAYMENT_NOT_FOUND")
    # A replacement proof may have been submitted while this durable job was waiting.
    # Never put a stale receipt in front of an admin with approval buttons.
    if row["latest_proof_id"] != proof_id:
        return {"superseded": True, "proof_id": proof_id_raw}
    if row["payment_status"] not in {"pending_review", "flagged"}:
        return {"superseded": True, "payment_status": row["payment_status"]}
    if existing is not None:
        return {"message_id": existing["ops_message_id"], "deduped": True}
    if not row["telegram_file_id"]:
        raise PermanentJobError("Payment proof has no Telegram file", code="PROOF_FILE_MISSING")

    topic_id = ctx.settings.zemen_ops_topic_payments
    caption = _review_caption(row)
    markup = payment_review_keyboard(payment_public_id=row["payment_public_id"])
    try:
        if row["telegram_media_type"] == "document":
            message = await ctx.bot.send_document(
                chat_id=group_id,
                message_thread_id=topic_id,
                document=row["telegram_file_id"],
                caption=caption,
                reply_markup=markup,
            )
        else:
            message = await ctx.bot.send_photo(
                chat_id=group_id,
                message_thread_id=topic_id,
                photo=row["telegram_file_id"],
                caption=caption,
                reply_markup=markup,
            )
    except Exception as exc:  # Telegram exception taxonomy is normalized here.
        mapped = _telegram_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise

    async with ctx.db.transaction() as conn:
        await repo.record_review_message(
            conn,
            payment_id=payment_id,
            proof_id=proof_id,
            chat_id=int(group_id),
            thread_id=int(topic_id) if topic_id else None,
            message_id=message.message_id,
        )
    return {"message_id": message.message_id, "payment": row["payment_public_id"]}


async def user_notify_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot is unavailable", code="BOT_UNAVAILABLE")
    try:
        telegram_id = int(job.payload["telegram_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PermanentJobError("Invalid telegram_id", code="BAD_PAYLOAD") from exc
    text = str(job.payload.get("text", "")).strip()
    if not text:
        raise PermanentJobError("User notification text is empty", code="BAD_PAYLOAD")
    reply_markup = None
    payment_action = str(job.payload.get("payment_action", ""))
    order_public_id = str(job.payload.get("order_public_id", ""))
    if payment_action in {"owned", "rejected", "review"} and order_public_id:
        reply_markup = payment_followup_keyboard(
            order_public_id=order_public_id,
            language="en" if job.payload.get("language") == "en" else "am",
            state=payment_action,
            mini_app_url=ctx.settings.mini_app_url if payment_action == "owned" else "",
        )
    try:
        message = await ctx.bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=reply_markup,
        )
    except Exception as exc:
        mapped = _telegram_error(exc)
        if mapped is not exc:
            raise mapped from exc
        raise
    return {"message_id": message.message_id, "telegram_id": telegram_id}


async def product_delivery_handler(ctx: WorkerContext, job: Job) -> dict[str, object]:
    if ctx.bot is None:
        raise PermanentJobError("Telegram bot is unavailable", code="BOT_UNAVAILABLE")
    entitlement_raw = str(job.payload.get("entitlement_id", ""))
    try:
        entitlement_id = UUID(entitlement_raw)
    except ValueError as exc:
        raise PermanentJobError("Invalid entitlement id", code="BAD_PAYLOAD") from exc

    ops = OperationsRepository()
    attempt_id: int | None = None
    async with ctx.db.transaction() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                e.*, u.telegram_id, u.preferred_language,
                o.public_id AS order_public_id,
                p.id AS product_id, p.slug,
                COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                pf.telegram_file_id, pf.file_name, pf.version
            FROM entitlements e
            JOIN users u ON u.id=e.user_id
            LEFT JOIN orders o ON o.id=e.granted_by_order_id
            JOIN products p ON p.id=e.product_id
            LEFT JOIN product_translations pt
                ON pt.product_id=p.id AND pt.language=COALESCE(u.preferred_language,'am')
            LEFT JOIN product_translations fallback
                ON fallback.product_id=p.id AND fallback.language=p.default_language
            LEFT JOIN product_files pf ON pf.id=e.product_file_id
            WHERE e.id=$1
            FOR UPDATE OF e
            """,
            entitlement_id,
        )
        if row is None:
            raise PermanentJobError("Entitlement not found", code="ENTITLEMENT_NOT_FOUND")
        if row["delivery_status"] == "delivered":
            return {"entitlement_id": entitlement_raw, "deduped": True}
        manual_override = bool(job.payload.get("actor"))
        if row["delivery_attempt_count"] >= ctx.settings.delivery_max_total_attempts and not manual_override:
            await ops.mark_delivery_failed(
                conn,
                entitlement_id=entitlement_id,
                error="Automatic delivery recovery limit reached",
            )
            raise PermanentJobError(
                "Automatic delivery recovery limit reached",
                code="DELIVERY_RECOVERY_LIMIT",
            )
        attempt_id = await ops.begin_delivery_attempt(
            conn, entitlement_id=entitlement_id, job_id=job.id, attempt_no=job.attempts
        )
        if not row["telegram_file_id"]:
            await ops.finish_delivery_attempt(
                conn,
                attempt_id=attempt_id,
                status="failed",
                error_code="PRODUCT_FILE_NOT_CONFIGURED",
                error_message="missing telegram_file_id",
            )
            await ops.mark_delivery_failed(
                conn, entitlement_id=entitlement_id, error="Product file is not configured"
            )
            raise PermanentJobError(
                "Product file is not configured with a Telegram file_id",
                code="PRODUCT_FILE_NOT_CONFIGURED",
            )

    language = "en" if row["preferred_language"] == "en" else "am"
    caption = (
        f"🎉 <b>{escape(row['product_title'])}</b> is yours.\n\nKeep this chat — you can also find your purchase in My Library. 📚"
        if language == "en"
        else f"🎉 <b>{escape(row['product_title'])}</b> የእርስዎ ሆኗል።\n\nይህን chat ያስቀምጡ፤ ምርቱን My Library ውስጥም ያገኙታል። 📚"
    )
    try:
        message = await ctx.bot.send_document(
            chat_id=int(row["telegram_id"]),
            document=row["telegram_file_id"],
            caption=caption,
            reply_markup=payment_followup_keyboard(
                order_public_id=str(row["order_public_id"] or ""),
                language=language,
                state="owned",
                mini_app_url=ctx.settings.mini_app_url,
            ),
        )
    except Exception as exc:
        mapped = _telegram_error(exc)
        error_code = getattr(mapped, "code", type(exc).__name__)
        terminal = isinstance(mapped, PermanentJobError) or job.final_attempt
        async with ctx.db.transaction() as conn:
            if attempt_id is not None:
                await ops.finish_delivery_attempt(
                    conn,
                    attempt_id=attempt_id,
                    status="failed" if terminal else "retrying",
                    error_code=str(error_code),
                    error_message=str(exc),
                )
            if terminal:
                await ops.mark_delivery_failed(conn, entitlement_id=entitlement_id, error=str(exc))
        if mapped is not exc:
            raise mapped from exc
        raise

    async with ctx.db.transaction() as conn:
        await conn.execute(
            """
            UPDATE entitlements
            SET delivery_status='delivered', delivered_at=now(), last_delivery_error=NULL,
                metadata=metadata || jsonb_build_object('telegram_message_id',$2::bigint)
            WHERE id=$1
            """,
            entitlement_id,
            message.message_id,
        )
        if attempt_id is not None:
            await ops.finish_delivery_attempt(
                conn,
                attempt_id=attempt_id,
                status="delivered",
                message_id=message.message_id,
            )
        await EventRepository().append(
            conn,
            event_type="PRODUCT_DELIVERED",
            user_id=row["user_id"],
            product_id=row["product_id"],
            order_id=row["granted_by_order_id"],
            payload={"entitlement_id": entitlement_raw, "telegram_message_id": message.message_id},
        )
    return {"entitlement_id": entitlement_raw, "message_id": message.message_id}
