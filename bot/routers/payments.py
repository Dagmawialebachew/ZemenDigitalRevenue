from __future__ import annotations

from html import escape
import re
from uuid import UUID

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.types import CallbackQuery, ForceReply, Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.users import UserRepository
from backend.services.payments import PaymentService
from bot.keyboards.payments import (
    external_checkout_keyboard,
    payment_followup_keyboard,
    payment_instructions_keyboard,
    payment_method_keyboard,
    payment_confirmation_keyboard,
    purchase_policy_keyboard,
    payment_reject_reason_keyboard,
    payment_review_keyboard,
)
from bot.services.current_user import load_current_entry_context
from bot.services.payment_copy import (
    checkout_intro,
    checkout_intro_from_resume,
    external_checkout_url,
    money,
    payment_instructions,
    payment_confirmation,
    resume_text,
)

router = Router(name="payments")

CUSTOM_REJECTION_CONTEXT = re.compile(
    r"CUSTOM_REJECTION_CONTEXT:(PAY-[A-F0-9]+):([0-9a-fA-F-]{36})"
)


async def _expected_review_proof(
    callback: CallbackQuery,
    service: PaymentService,
    *,
    payment_public_id: str,
) -> UUID:
    if callback.message is None:
        raise LookupError("review message unavailable")
    return await service.review_proof_for_message(
        payment_public_id=payment_public_id,
        chat_id=int(callback.message.chat.id),
        message_id=int(callback.message.message_id),
    )


def _methods(settings: Settings) -> tuple[bool, bool]:
    return bool(settings.cbe_account_number.strip()), bool(settings.telebirr_number.strip())


async def send_checkout(
    *,
    message: Message,
    db: Database,
    settings: Settings,
    user_id: object,
    product_slug: str,
) -> None:
    service = PaymentService(db, settings)
    checkout = await service.create_checkout(user_id=user_id, product_slug=product_slug)
    language = "am"
    async with db.acquire() as conn:
        user = await UserRepository().get_by_id(conn, user_id=user_id)
        if user and user["preferred_language"] == "en":
            language = "en"

    if not settings.manual_payment_in_telegram_enabled:
        if settings.external_manual_checkout_url:
            url = external_checkout_url(settings.external_manual_checkout_url, checkout.public_id)
            await message.answer(
                checkout_intro(checkout, language=language),
                reply_markup=external_checkout_keyboard(url=url, language=language),
            )
            return
        await message.answer(
            (
                "⚠️ <b>Checkout isn't available right now.</b> Please contact support."
                if language == "en"
                else "⚠️ <b>ክፍያ አሁን አይገኝም።</b> እባክዎ support ያነጋግሩ።"
            )
        )
        return

    cbe, telebirr = _methods(settings)
    if not (cbe or telebirr):
        await message.answer(
            "⚠️ Payment destinations are not configured yet."
            if language == "en"
            else "⚠️ የክፍያ መቀበያዎች ገና አልተዘጋጁም።"
        )
        return
    await message.answer(
        checkout_intro(checkout, language=language),
        reply_markup=payment_method_keyboard(
            order_public_id=checkout.public_id,
            language=language,
            cbe_enabled=cbe,
            telebirr_enabled=telebirr,
        ),
    )


async def send_order_resume(
    *,
    message: Message,
    db: Database,
    settings: Settings,
    user_id: object,
    order_public_id: str,
) -> None:
    service = PaymentService(db, settings)
    resume = await service.resume_order_for_user(user_id=user_id, order_public_id=order_public_id)
    if resume.order_status == "paid" or resume.payment_status == "approved":
        await message.answer(
            (
                f"✅ <b>This order is already paid.</b>\n\n📦 {escape(resume.product_title)}\n\nYour product is available in My Library. 📚"
                if resume.language == "en"
                else f"✅ <b>ይህ ትዕዛዝ ክፍያው ተረጋግጧል።</b>\n\n📦 {escape(resume.product_title)}\n\nምርትዎ My Library ውስጥ ይገኛል። 📚"
            ),
            reply_markup=payment_followup_keyboard(
                order_public_id=resume.order_public_id,
                language=resume.language,
                state="owned",
                mini_app_url=settings.mini_app_url,
            ),
        )
        return
    if resume.order_status in {"cancelled", "expired", "refunded"}:
        await message.answer(
            "⚠️ This checkout is no longer active. Please open the product and start a new checkout."
            if resume.language == "en"
            else "⚠️ ይህ checkout ከእንግዲህ አይሰራም። ምርቱን እንደገና ከፍተው አዲስ checkout ይጀምሩ።"
        )
        return
    if not resume.policies_accepted:
        await message.answer(
            resume_text(resume),
            reply_markup=purchase_policy_keyboard(
                order_public_id=resume.order_public_id,
                language=resume.language,
            ),
        )
        return
    if resume.payment_status in {"pending_review", "flagged", "rejected"}:
        await message.answer(
            resume_text(resume),
            reply_markup=payment_followup_keyboard(
                order_public_id=resume.order_public_id,
                language=resume.language,
                state="rejected" if resume.payment_status == "rejected" else "review",
            ),
        )
        return
    if resume.payment_status == "awaiting_proof" and resume.payment_method:
        text, destination = payment_instructions(resume=resume, settings=settings)
        await message.answer(
            text,
            reply_markup=payment_instructions_keyboard(
                payment_public_id=resume.payment_public_id or "",
                destination=destination,
                amount_text=money(resume.total_due_br),
                language=resume.language,
            ),
        )
        return
    cbe, telebirr = _methods(settings)
    await message.answer(
        resume_text(resume),
        reply_markup=payment_method_keyboard(
            order_public_id=resume.order_public_id,
            language=resume.language,
            cbe_enabled=cbe,
            telebirr_enabled=telebirr,
        ),
    )


@router.callback_query(F.data.startswith("pay:status:"))
async def payment_status(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    order_public_id = callback.data.split(":", 2)[2]
    await callback.answer("🔄")
    try:
        await send_order_resume(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
            order_public_id=order_public_id,
        )
    except (LookupError, ValueError):
        await callback.message.answer(
            "⚠️ This checkout is no longer active."
            if current.language_for_copy == "en"
            else "⚠️ ይህ checkout ከእንግዲህ አይሰራም።"
        )


@router.callback_query(F.data.startswith("pay:method:"))
async def choose_payment_method(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer("Invalid payment action", show_alert=True)
        return
    _, _, order_public_id, method = parts
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    await callback.answer("✅")
    await callback.message.answer(
        payment_confirmation(method=method, language=current.language_for_copy),
        reply_markup=payment_confirmation_keyboard(
            order_public_id=order_public_id,
            method=method,
            language=current.language_for_copy,
        ),
    )


@router.callback_query(F.data.startswith("pay:back:"))
async def back_to_payment_methods(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    order_public_id = callback.data.split(":", 2)[2]
    cbe, telebirr = _methods(settings)
    await callback.answer()
    await callback.message.answer(
        checkout_intro_from_resume(await PaymentService(db, settings).resume_order_for_user(
            user_id=current.user_id,
            order_public_id=order_public_id,
        )),
        reply_markup=payment_method_keyboard(
            order_public_id=order_public_id,
            language=current.language_for_copy,
            cbe_enabled=cbe,
            telebirr_enabled=telebirr,
        ),
    )


@router.callback_query(F.data.startswith("pay:confirm:"))
async def confirm_payment_method(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await callback.answer("Invalid payment action", show_alert=True)
        return
    _, _, order_public_id, method = parts
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    service = PaymentService(db, settings)
    try:
        await service.accept_purchase_policies(
            user_id=current.user_id,
            order_public_id=order_public_id,
            language=current.language_for_copy,
        )
        resume = await service.select_method(
            user_id=current.user_id,
            order_public_id=order_public_id,
            method_value=method,
        )
        text, destination = payment_instructions(resume=resume, settings=settings)
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("✅")
    await callback.message.answer(
        text,
        reply_markup=payment_instructions_keyboard(
            payment_public_id=resume.payment_public_id or "",
            destination=destination,
            amount_text=money(resume.total_due_br),
            language=resume.language,
        ),
    )


@router.callback_query(F.data.startswith("pay:accept:"))
async def accept_purchase_policies(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    order_public_id = callback.data.split(":", 2)[2]
    language = current.language_for_copy
    try:
        resume = await PaymentService(db, settings).accept_purchase_policies(
            user_id=current.user_id,
            order_public_id=order_public_id,
            language=language,
        )
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    cbe, telebirr = _methods(settings)
    if not (cbe or telebirr):
        await callback.answer("Payment destinations are not configured", show_alert=True)
        return
    await callback.answer("✅")
    await callback.message.answer(
        resume_text(resume),
        reply_markup=payment_method_keyboard(
            order_public_id=resume.order_public_id,
            language=language,
            cbe_enabled=cbe,
            telebirr_enabled=telebirr,
        ),
    )


@router.callback_query(F.data.startswith("pay:paid:"))
async def paid_ready_for_proof(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    payment_public_id = callback.data.split(":", 2)[2]
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    async with db.transaction() as conn:
        payment = await PaymentService(db, settings).repo.payment_by_public_id_for_user(
            conn,
            public_id=payment_public_id,
            user_id=current.user_id,
        )
        if payment is None:
            await callback.answer("Payment not found", show_alert=True)
            return
        if payment["status"] in {"pending_review", "flagged"}:
            await callback.answer("Already under review", show_alert=True)
            return
        if payment["status"] == "approved":
            await callback.answer("Already approved", show_alert=True)
            return
        await conn.execute(
            """
            UPDATE conversation_sessions
            SET active_flow='payment', step_key='awaiting_proof',
                active_order_id=$2, active_payment_id=$3,
                last_interaction_at=now(), updated_at=now()
            WHERE user_id=$1
            """,
            current.user_id,
            payment["order_id"],
            payment["id"],
        )
    await callback.answer("📸")
    language = current.preferred_language or "am"
    await callback.message.answer(
        (
            "📸 <b>Send the payment screenshot here.</b>\n\nMake sure the amount, receiver and transaction details are visible."
            if language == "en"
            else "📸 <b>Payment screenshotዎን እዚህ ይላኩ።</b>\n\nመጠኑ፣ ተቀባዩ እና transaction መረጃው በግልጽ እንዲታይ ያድርጉ።"
        )
    )


async def _accept_proof(
    *,
    message: Message,
    db: Database,
    settings: Settings,
    file_id: str,
    file_unique_id: str | None,
    media_type: str,
) -> None:
    if message.from_user is None:
        raise SkipHandler

    current = await load_current_entry_context(db, telegram_user=message.from_user)
    if current is None:
        raise SkipHandler

    service = PaymentService(db, settings)
    try:
        result = await service.submit_proof(
            user_id=current.user_id,
            telegram_file_id=file_id,
            telegram_file_unique_id=file_unique_id,
            telegram_media_type=media_type,
            caption=message.caption,
        )
    except LookupError:
        # This image/document is not an active payment proof.
        # Let Support or the final fallback router receive it.
        raise SkipHandler
    except ValueError as exc:
        language = current.preferred_language or "am"
        await message.answer(
            f"ℹ️ {escape(str(exc))}"
            if language == "en"
            else "ℹ️ ክፍያዎ አሁን በማረጋገጥ ላይ ነው። ተጨማሪ screenshot አያስፈልግም።"
        )
        return
    language = current.preferred_language or "am"
    if result.flagged:
        # Do not accuse the customer. Duplicate is only an internal review signal.
        text = (
            "✅ <b>Receipt received.</b>\n\nOur team is reviewing it now. We'll reply here as soon as it's confirmed. 🔎"
            if language == "en"
            else "✅ <b>Receiptዎ ደርሶናል።</b>\n\nአሁን በማረጋገጥ ላይ ነው፤ ሲረጋገጥ እዚሁ እናሳውቅዎታለን። 🔎"
        )
    else:
        text = (
            "✅ <b>Receipt received.</b>\n\nWe're verifying your payment now. You don't need to send anything else. 🔎"
            if language == "en"
            else "✅ <b>Receiptዎ ደርሶናል።</b>\n\nክፍያዎን እያረጋገጥን ነው። ሌላ ምንም መላክ አያስፈልግዎትም። 🔎"
        )
    await message.answer(
        text,
        reply_markup=payment_followup_keyboard(
            order_public_id=result.order_public_id,
            language=language,
            state="review",
        ),
    )


@router.message(F.photo)
async def payment_photo(message: Message, db: Database, settings: Settings) -> None:
    if not message.photo:
        return
    photo = message.photo[-1]
    await _accept_proof(
        message=message,
        db=db,
        settings=settings,
        file_id=photo.file_id,
        file_unique_id=photo.file_unique_id,
        media_type="photo",
    )


@router.message(F.document & F.document.mime_type.startswith("image/"))
async def payment_image_document(message: Message, db: Database, settings: Settings) -> None:
    if message.document is None:
        return
    await _accept_proof(
        message=message,
        db=db,
        settings=settings,
        file_id=message.document.file_id,
        file_unique_id=message.document.file_unique_id,
        media_type="document",
    )


@router.callback_query(F.data.startswith("ops:pay:approve:"))
async def ops_approve(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    payment_public_id = callback.data.rsplit(":", 1)[-1] if callback.data else ""
    service = PaymentService(db, settings)
    try:
        expected_proof_id = await _expected_review_proof(
            callback, service, payment_public_id=payment_public_id
        )
        result = await service.approve(
            payment_public_id=payment_public_id,
            admin_telegram_id=callback.from_user.id,
            expected_proof_id=expected_proof_id,
        )
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("✅ Approved" if result.changed else "Already approved")
    if callback.message:
        caption = callback.message.caption or ""
        status_line = f"\n\n✅ <b>APPROVED</b> · by {escape(callback.from_user.full_name)}"
        try:
            await callback.message.edit_caption(
                caption=(caption + status_line)[:1024],
                reply_markup=None,
            )
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass


@router.callback_query(F.data.startswith("ops:pay:reject:"))
async def ops_reject_menu(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    payment_public_id = callback.data.rsplit(":", 1)[-1] if callback.data else ""
    service = PaymentService(db, settings)
    try:
        await _expected_review_proof(callback, service, payment_public_id=payment_public_id)
        allowed, _ = await service.is_admin(telegram_id=callback.from_user.id)
        if not allowed:
            raise PermissionError
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("Choose a reason")
    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=payment_reject_reason_keyboard(payment_public_id=payment_public_id)
        )


@router.callback_query(F.data.startswith("ops:pay:review:"))
async def ops_review_menu(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    payment_public_id = callback.data.rsplit(":", 1)[-1] if callback.data else ""
    service = PaymentService(db, settings)
    try:
        await _expected_review_proof(callback, service, payment_public_id=payment_public_id)
        allowed, _ = await service.is_admin(telegram_id=callback.from_user.id)
        if not allowed:
            raise PermissionError
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=payment_review_keyboard(payment_public_id=payment_public_id)
        )


@router.callback_query(F.data.startswith("ops:pay:reason:"))
async def ops_reject_reason(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":", 4)
    if len(parts) != 5:
        await callback.answer("Invalid action", show_alert=True)
        return
    payment_public_id, reason = parts[3], parts[4]
    service = PaymentService(db, settings)
    try:
        expected_proof_id = await _expected_review_proof(
            callback, service, payment_public_id=payment_public_id
        )
        allowed, _ = await service.is_admin(telegram_id=callback.from_user.id)
        if not allowed:
            raise PermissionError
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    if reason == "other":
        await callback.answer("✏️ Type the reason")
        if callback.message:
            await callback.message.reply(
                "✏️ <b>Custom rejection reason</b>\n\n"
                "Reply to this message with the exact reason the customer should see.\n\n"
                f"<code>CUSTOM_REJECTION_CONTEXT:{payment_public_id}:{expected_proof_id}</code>",
                reply_markup=ForceReply(
                    selective=True,
                    input_field_placeholder="Why are we rejecting this payment?",
                ),
            )
        return

    try:
        result = await service.reject(
            payment_public_id=payment_public_id,
            reason_value=reason,
            admin_telegram_id=callback.from_user.id,
            expected_proof_id=expected_proof_id,
        )
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("❌ Rejected" if result.changed else "Already rejected")
    if callback.message:
        caption = callback.message.caption or ""
        status_line = (
            f"\n\n❌ <b>REJECTED</b> · {escape(reason.replace('_', ' '))} "
            f"· by {escape(callback.from_user.full_name)}"
        )
        try:
            await callback.message.edit_caption(
                caption=(caption + status_line)[:1024], reply_markup=None
            )
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass


@router.message(
    F.text
    & F.reply_to_message
    & F.reply_to_message.text.contains("CUSTOM_REJECTION_CONTEXT:")
)
async def ops_custom_rejection_reason(
    
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None or message.reply_to_message is None or not message.text:
        return
    source = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = CUSTOM_REJECTION_CONTEXT.search(source)
    if match is None:
        return
    payment_public_id = match.group(1)
    try:
        expected_proof_id = UUID(match.group(2))
    except ValueError:
        await message.reply("⚠️ Invalid review context.")
        return
    reason_text = message.text.strip()
    if len(reason_text) < 3:
        await message.reply("⚠️ Please give a clear rejection reason.")
        return
    if len(reason_text) > 500:
        await message.reply("⚠️ Keep the reason under 500 characters.")
        return

    service = PaymentService(db, settings)
    try:
        result = await service.reject(
            payment_public_id=payment_public_id,
            reason_value="other",
            reason_text=reason_text,
            admin_telegram_id=message.from_user.id,
            expected_proof_id=expected_proof_id,
        )
    except PermissionError:
        await message.reply("Not authorized")
        return
    except (LookupError, ValueError) as exc:
        await message.reply(f"⚠️ {escape(str(exc))}")
        return

    # Remove actions from the original review card even though this rejection was
    # completed through a ForceReply prompt.
    async with db.acquire() as conn:
        review = await conn.fetchrow(
            """
            SELECT prm.ops_chat_id, prm.ops_message_id
            FROM payment_review_messages prm
            JOIN payments p ON p.id=prm.payment_id
            WHERE p.public_id=$1 AND prm.proof_id=$2
            ORDER BY prm.created_at DESC LIMIT 1
            """,
            payment_public_id,
            expected_proof_id,
        )
    if review is not None:
        try:
            await message.bot.edit_message_reply_markup(
                chat_id=int(review["ops_chat_id"]),
                message_id=int(review["ops_message_id"]),
                reply_markup=None,
            )
        except Exception:
            pass
    await message.reply(
        f"❌ <b>{payment_public_id}</b> rejected. Customer was told the reason."
        if result.changed
        else f"ℹ️ <b>{payment_public_id}</b> was already rejected."
    )


@router.callback_query(F.data.startswith("ops:pay:flag:"))
async def ops_flag(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    payment_public_id = callback.data.rsplit(":", 1)[-1] if callback.data else ""
    service = PaymentService(db, settings)
    try:
        expected_proof_id = await _expected_review_proof(
            callback, service, payment_public_id=payment_public_id
        )
        result = await service.flag(
            payment_public_id=payment_public_id,
            admin_telegram_id=callback.from_user.id,
            expected_proof_id=expected_proof_id,
        )
    except PermissionError:
        await callback.answer("Not authorized", show_alert=True)
        return
    except (LookupError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    await callback.answer("⚠️ Flagged" if result.changed else "Already flagged")
    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=payment_review_keyboard(payment_public_id=payment_public_id)
        )
