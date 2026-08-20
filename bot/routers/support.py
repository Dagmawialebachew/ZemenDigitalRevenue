from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, User

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.operations import OperationsService
from bot.services.current_user import load_current_entry_context


router = Router(name="support")


def _attachment_from_message(message: Message) -> dict[str, object] | None:
    if message.photo:
        photo = message.photo[-1]
        return {
            "type": "photo",
            "telegram_file_id": photo.file_id,
            "telegram_file_unique_id": photo.file_unique_id,
        }

    if message.document:
        document = message.document
        return {
            "type": "document",
            "telegram_file_id": document.file_id,
            "telegram_file_unique_id": document.file_unique_id,
            "file_name": document.file_name,
            "mime_type": document.mime_type,
        }

    return None


async def _open_support(
    message: Message,
    telegram_user: User,
    db: Database,
    settings: Settings,
) -> None:
    current = await load_current_entry_context(
        db,
        telegram_user=telegram_user,
    )

    if current is None:
        await message.answer("👋 Send /start first.")
        return

    case = await OperationsService(db, settings).open_support(
        user_id=current.user_id,
    )

    if current.language_for_copy == "en":
        text = (
            "💬 <b>Zemen Support</b>\n\n"
            f"Your support case is <code>{case['public_id']}</code>.\n\n"
            "Send your question, screenshot, photo, or document here. "
            "Our team will receive it in ZEMEN OPS and reply in this chat."
        )
    else:
        text = (
            "💬 <b>Zemen Support</b>\n\n"
            f"Support caseዎ <code>{case['public_id']}</code> ነው።\n\n"
            "ጥያቄዎን፣ screenshot፣ photo ወይም document እዚህ ይላኩ። "
            "ቡድናችን ZEMEN OPS ውስጥ ይቀበለዋል፤ ምላሹንም እዚሁ ያገኛሉ።"
        )

    await message.answer(text)


# ---------------------------------------------------------------------------
# CUSTOMER — OPEN SUPPORT
# ---------------------------------------------------------------------------

@router.message(Command("help"))
async def support_command(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.chat.type != "private" or message.from_user is None:
        raise SkipHandler

    await _open_support(
        message,
        message.from_user,
        db,
        settings,
    )


@router.callback_query(F.data == "menu:help")
async def support_menu(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None:
        await callback.answer()
        return

    if callback.message.chat.type != "private":
        await callback.answer()
        return

    await callback.answer()
    await _open_support(
        callback.message,
        callback.from_user,
        db,
        settings,
    )


# ---------------------------------------------------------------------------
# OPS — ADMIN REPLY MODE
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("ops:support:reply:"))
async def ops_support_reply(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Not authorized", show_alert=True)
        return

    if not callback.data or callback.message is None:
        await callback.answer()
        return

    if (
        settings.zemen_ops_group_id
        and int(callback.message.chat.id) != int(settings.zemen_ops_group_id)
    ):
        await callback.answer("This action only works in ZEMEN OPS.", show_alert=True)
        return

    case_public_id = callback.data.rsplit(":", 1)[-1]

    async with db.transaction() as conn:
        case = await conn.fetchrow(
            """
            SELECT id, status
            FROM support_cases
            WHERE public_id=$1
            """,
            case_public_id,
        )

        if case is None:
            await callback.answer("Support case not found", show_alert=True)
            return

        if case["status"] not in {"open", "waiting_customer", "waiting_admin"}:
            await callback.answer("This support case is already resolved.", show_alert=True)
            return

        thread_id = (
            callback.message.message_thread_id
            if callback.message.message_thread_id is not None
            else settings.zemen_ops_topic_support
        )

        await conn.execute(
            """
            INSERT INTO support_reply_contexts (
                admin_telegram_id,
                case_id,
                ops_chat_id,
                message_thread_id,
                created_at,
                expires_at
            )
            VALUES ($1, $2, $3, $4, now(), now() + INTERVAL '30 minutes')
            ON CONFLICT (admin_telegram_id)
            DO UPDATE SET
                case_id=EXCLUDED.case_id,
                ops_chat_id=EXCLUDED.ops_chat_id,
                message_thread_id=EXCLUDED.message_thread_id,
                created_at=now(),
                expires_at=now() + INTERVAL '30 minutes'
            """,
            callback.from_user.id,
            case["id"],
            int(callback.message.chat.id),
            int(thread_id) if thread_id is not None else None,
        )

    await callback.answer("💬 Reply mode enabled")

    await callback.message.answer(
        f"💬 <b>Replying to {escape(case_public_id)}</b>\n\n"
        "Send your next text message in this Support topic. "
        "It will be delivered to the customer."
    )


@router.message(
    F.text,
    F.chat.type.in_({"group", "supergroup"}),
)
async def ops_support_pending_reply(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None or not message.text:
        raise SkipHandler

    if message.from_user.id not in settings.admin_telegram_ids:
        raise SkipHandler

    if not settings.zemen_ops_group_id:
        raise SkipHandler

    if int(message.chat.id) != int(settings.zemen_ops_group_id):
        raise SkipHandler

    async with db.acquire() as conn:
        pending = await conn.fetchrow(
            """
            SELECT
                src.case_id,
                src.ops_chat_id,
                src.message_thread_id,
                sc.public_id,
                sc.status
            FROM support_reply_contexts src
            JOIN support_cases sc ON sc.id=src.case_id
            WHERE src.admin_telegram_id=$1
              AND src.expires_at > now()
            """,
            message.from_user.id,
        )

    if pending is None:
        raise SkipHandler

    if int(pending["ops_chat_id"]) != int(message.chat.id):
        raise SkipHandler

    expected_thread_id = pending["message_thread_id"]
    actual_thread_id = message.message_thread_id

    if expected_thread_id is not None:
        if actual_thread_id is None or int(expected_thread_id) != int(actual_thread_id):
            raise SkipHandler

    if pending["status"] not in {"open", "waiting_customer", "waiting_admin"}:
        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM support_reply_contexts WHERE admin_telegram_id=$1",
                message.from_user.id,
            )
        await message.reply("ℹ️ This support case is already resolved.")
        return

    reply_text = message.text.strip()
    if not reply_text:
        await message.reply("⚠️ Reply cannot be empty.")
        return

    try:
        await OperationsService(db, settings).admin_reply_support(
            case_public_id=pending["public_id"],
            admin_telegram_id=message.from_user.id,
            text=reply_text,
        )
    except PermissionError:
        await message.reply("⛔ Not authorized.")
        return
    except (LookupError, ValueError) as exc:
        await message.reply(f"⚠️ {escape(str(exc))}")
        return

    async with db.transaction() as conn:
        await conn.execute(
            """
            DELETE FROM support_reply_contexts
            WHERE admin_telegram_id=$1
              AND case_id=$2
            """,
            message.from_user.id,
            pending["case_id"],
        )

    await message.reply("✅ Reply sent to the customer.")


# ---------------------------------------------------------------------------
# OPS — RESOLVE SUPPORT CASE
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("ops:support:resolve:"))
async def ops_support_resolve(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Not authorized", show_alert=True)
        return

    if not callback.data:
        await callback.answer()
        return

    case_public_id = callback.data.rsplit(":", 1)[-1]

    try:
        await OperationsService(db, settings).resolve_support(
            case_public_id=case_public_id,
            admin_telegram_id=callback.from_user.id,
        )
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    await callback.answer("✅ Resolved")

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CUSTOMER — MESSAGE WHILE SUPPORT IS ACTIVE
# ---------------------------------------------------------------------------

@router.message(
    F.text | F.photo | F.document,
    F.chat.type == "private",
)
async def support_customer_message(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None:
        raise SkipHandler

    current = await load_current_entry_context(
        db,
        telegram_user=message.from_user,
    )

    if current is None:
        raise SkipHandler

    async with db.acquire() as conn:
        session = await conn.fetchrow(
            """
            SELECT active_flow, step_key
            FROM conversation_sessions
            WHERE user_id=$1
            """,
            current.user_id,
        )

    if session is None or session["active_flow"] != "support":
        # This is important: do not consume ordinary customer messages.
        # Let the final fallback router decide what to do with them.
        raise SkipHandler

    try:
        await OperationsService(db, settings).submit_support_message(
            user_id=current.user_id,
            telegram_message_id=message.message_id,
            body=message.text or message.caption,
            attachment=_attachment_from_message(message),
        )
    except LookupError:
        # State changed between the read above and the transaction.
        # Let fallback reopen/reuse Support and submit the same update.
        raise SkipHandler

    if current.language_for_copy == "en":
        await message.answer(
            "✅ <b>Received.</b> Zemen Support will reply here."
        )
    else:
        await message.answer(
            "✅ <b>ደርሶናል።</b> Zemen Support እዚሁ ይመልስልዎታል።"
        )
