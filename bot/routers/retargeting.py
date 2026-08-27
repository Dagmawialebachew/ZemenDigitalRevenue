from __future__ import annotations

from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.marketing import normalize_audience
from backend.repositories.products import ProductRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.services.marketing import MarketingService
from backend.services.salesman import SalesmanService
from bot.keyboards.primitives import inline_action
from bot.services.current_user import load_current_entry_context
from bot.services.product_media import send_sample_pdf, send_sales_gallery
from scripts.retargeting import _callback_buttons, _callback_buttons_en, retargeting_copy

router = Router(name="retargeting")
PRODUCT_SLUG = "ai-kezero"
CAMPAIGN_NAME = "High-Intent Retargeting · AI ከዜሮ"


def _is_admin(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_telegram_ids)


def _launch_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(text="📨 Send exact preview to admins", callback_data="retarget:send_preview", style=None),
    )
    builder.row(
        inline_action(text="🚀 Launch retargeting", callback_data="retarget:launch", style=None),
        inline_action(text="✖ Cancel", callback_data="retarget:cancel", style=None),
    )
    return builder.as_markup()


def _preview_keyboard(settings: Settings, *, language: str) -> InlineKeyboardMarkup:
    buttons = _callback_buttons() if language == "am" else _callback_buttons_en()
    builder = InlineKeyboardBuilder()
    for button in buttons:
        builder.row(inline_action(text=button["text"], callback_data=button["callback_data"], style=None))
    return builder.as_markup()


async def _run_retarget_action(*, message: Message, db: Database, settings: Settings, user_id: object, action: str) -> None:
    async with db.transaction() as conn:
        product = await ProductRepository().get_active_by_slug(conn, PRODUCT_SLUG)
        if product is None:
            raise LookupError(f"Active product not found: {PRODUCT_SLUG}")
        await ConversationSessionRepository().set_focus_product(conn, user_id=user_id, product_id=product["id"])

    if action == "buy":
        from bot.routers.payments import send_checkout

        await send_checkout(message=message, db=db, settings=settings, user_id=user_id, product_slug=PRODUCT_SLUG)
        return

    detail = await SalesmanService(db).detail(user_id=user_id, kind="preview")
    if action == "preview":
        if not await send_sales_gallery(message=message, presentation=detail.presentation, settings=settings):
            await message.answer("The product preview is not available right now.")
        return
    if action == "sample":
        if not await send_sample_pdf(message=message, presentation=detail.presentation, settings=settings, reply_markup=None):
            await message.answer(
                "📄 The sample is not available right now."
                if detail.presentation.language == "en"
                else "📄 ሳምፕሉ አሁን አይገኝም።"
            )
        return
    raise ValueError("Unknown retargeting action")


def _report_keyboard(broadcast_id: UUID) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        inline_action(
            text="📊 View report",
            callback_data=f"retarget:report:{broadcast_id}",
            style=None,
        ),
        inline_action(
            text="🔄 Refresh",
            callback_data=f"retarget:report:{broadcast_id}",
            style=None,
        ),
    )
    return builder.as_markup()


def _report_text(report: dict[str, object]) -> str:
    recipients = int(report.get("recipients") or 0)
    sent = int(report.get("sent_count") or 0)
    blocked = int(report.get("blocked_count") or 0)
    failed = int(report.get("failed_count") or 0)
    skipped = int(report.get("skipped_count") or 0)
    clickers = int(report.get("clickers") or 0)
    conversions = int(report.get("conversions") or 0)
    revenue = report.get("revenue_br") or "0"
    delivery_rate = sent / recipients * 100 if recipients else 0
    click_rate = clickers / sent * 100 if sent else 0
    conversion_rate = conversions / clickers * 100 if clickers else 0
    return (
        "📊 <b>Retargeting report</b>\n\n"
        f"<b>{escape(str(report.get('name') or 'Broadcast'))}</b>\n"
        f"Status: <code>{escape(str(report.get('status') or 'unknown'))}</code>\n\n"
        f"👥 Audience snapshot: <code>{recipients}</code>\n"
        f"✅ Sent: <code>{sent}</code> ({delivery_rate:.1f}%)\n"
        f"🚫 Blocked: <code>{blocked}</code>\n"
        f"⚠️ Failed: <code>{failed}</code>\n"
        f"⏭ Skipped: <code>{skipped}</code>\n\n"
        f"🖱 Clickers: <code>{clickers}</code> ({click_rate:.1f}% of sent)\n"
        f"💰 Paid conversions: <code>{conversions}</code> ({conversion_rate:.1f}% of clickers)\n"
        f"💵 Paid revenue: <code>{escape(str(revenue))} Br</code>\n\n"
        "Use the rates to identify the bottleneck: delivery, click-through, or checkout conversion."
    )


@router.message(Command("retarget"))
async def retarget_command(message: Message, db: Database, settings: Settings) -> None:
    if not _is_admin(message, settings):
        return
    async with db.acquire() as conn:
        product = await conn.fetchrow(
            "SELECT id,slug,status,regular_price_br FROM products WHERE slug=$1 LIMIT 1",
            PRODUCT_SLUG,
        )
    if product is None or product["status"] != "active":
        await message.answer(f"⚠️ Active product not found: <code>{PRODUCT_SLUG}</code>")
        return
    audience = normalize_audience({"kind": "everyone"})
    count = await MarketingService(db, settings).audience_count(audience.as_dict())
    am_text, en_text = retargeting_copy()
    await message.answer(
        "🎯 <b>Retargeting preview</b>\n\n"
        f"Product: <code>{escape(PRODUCT_SLUG)}</code>\n"
        f"Audience: <code>{count}</code> all active reachable bot users\n"
        "This includes previous buyers.\n"
        "Format: text-only\n\n"
        f"<b>AM copy:</b>\n{am_text}\n\n"
        f"<b>EN copy:</b>\n{en_text}\n\n"
        "No message will be sent until you press Launch.",
        reply_markup=_launch_keyboard(),
    )


@router.callback_query(F.data == "retarget:cancel")
async def cancel_retarget(callback: CallbackQuery, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer()
        return
    await callback.answer("Cancelled")
    if callback.message:
        await callback.message.edit_text("Retargeting cancelled. No broadcast was created.")


@router.callback_query(F.data == "retarget:send_preview")
async def send_retarget_preview_to_admins(callback: CallbackQuery, bot: Bot, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer()
        return
    am_text, en_text = retargeting_copy()
    sent = 0
    for admin_id in settings.admin_telegram_ids:
        await bot.send_message(
            chat_id=admin_id,
            text=am_text,
            reply_markup=_preview_keyboard(settings, language="am"),
        )
        await bot.send_message(
            chat_id=admin_id,
            text=en_text,
            reply_markup=_preview_keyboard(settings, language="en"),
        )
        sent += 1
    await callback.answer(f"Preview sent to {sent} admin(s)")


async def _dispatch_retarget_action(
    *, message: Message, db: Database, settings: Settings, user_id: object, action: str
) -> None:
    await _run_retarget_action(
        message=message,
        db=db,
        settings=settings,
        user_id=user_id,
        action=action,
    )


@router.callback_query(F.data.startswith("broadcast:click:"))
async def broadcast_retarget_click(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    token = callback.data.removeprefix("broadcast:click:")
    async with db.transaction() as conn:
        click = await conn.fetchrow(
            "SELECT button_key FROM broadcast_click_links WHERE token=$1 AND user_id=$2 FOR UPDATE",
            token,
            current.user_id,
        )
        if click is None:
            await callback.answer("This button has expired", show_alert=True)
            return
        await conn.execute(
            """UPDATE broadcast_click_links
               SET click_count=click_count+1, clicked_at=COALESCE(clicked_at,now()),
                   first_clicked_at=COALESCE(first_clicked_at,now()), updated_at=now()
               WHERE token=$1 AND user_id=$2""",
            token,
            current.user_id,
        )
    await callback.answer()
    try:
        await _dispatch_retarget_action(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
            action=str(click["button_key"]),
        )
    except (LookupError, ValueError) as exc:
        await callback.message.answer(str(exc))


@router.callback_query(F.data.startswith("retarget:action:"))
async def admin_preview_retarget_click(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    current = await load_current_entry_context(db, telegram_user=callback.from_user)
    if current is None:
        await callback.answer("Please restart the bot", show_alert=True)
        return
    action = callback.data.removeprefix("retarget:action:")
    await callback.answer()
    try:
        await _dispatch_retarget_action(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
            action=action,
        )
    except (LookupError, ValueError) as exc:
        await callback.message.answer(str(exc))


@router.callback_query(F.data == "retarget:launch")
async def launch_retarget(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer()
        return
    await callback.answer("Launching")
    service = MarketingService(db, settings)
    try:
        async with db.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id,slug,status FROM products WHERE slug=$1 LIMIT 1",
                PRODUCT_SLUG,
            )
        if product is None or product["status"] != "active":
            raise LookupError(f"Active product not found: {PRODUCT_SLUG}")
        audience = normalize_audience({"kind": "everyone"})
        count = await service.audience_count(audience.as_dict())
        if count == 0:
            raise ValueError("No active reachable bot users")
        am_text, en_text = retargeting_copy()
        broadcast = await service.create_broadcast(
            admin_telegram_id=callback.from_user.id,
            data={
                "name": CAMPAIGN_NAME,
                "audience_definition": audience.as_dict(),
                "content_am": {"text": am_text, "buttons": _callback_buttons()},
                "content_en": {"text": en_text, "buttons": _callback_buttons_en()},
            },
        )
        scheduled = await service.schedule_broadcast(
            broadcast_id=UUID(str(broadcast["id"])),
            admin_telegram_id=callback.from_user.id,
            scheduled_at=None,
        )
        if callback.message:
            await callback.message.edit_text(
                "✅ <b>Retargeting scheduled</b>\n\n"
                f"Broadcast: <code>{broadcast['id']}</code>\n"
                f"Recipients: <code>{scheduled['audience_snapshot_count']}</code>\n\n"
                "The durable worker is dispatching the message now. Use the buttons below to inspect progress."
                f"\n\nYou can also run <code>/retarget_report {broadcast['id']}</code>."
                ,
                reply_markup=_report_keyboard(UUID(str(broadcast["id"]))),
            )
    except (LookupError, ValueError) as exc:
        if callback.message:
            await callback.message.edit_text(f"⚠️ Retargeting was not launched: {escape(str(exc))}")


@router.callback_query(F.data.startswith("retarget:report:"))
async def retarget_report_callback(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer()
        return
    try:
        broadcast_id = UUID(callback.data.removeprefix("retarget:report:"))
        report = await MarketingService(db, settings).broadcast_report(broadcast_id)
    except (ValueError, LookupError):
        await callback.answer("Report unavailable", show_alert=True)
        return
    await callback.answer("Report refreshed")
    if callback.message:
        try:
            await callback.message.edit_text(
                _report_text(report),
                reply_markup=_report_keyboard(broadcast_id),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise


@router.message(Command("retarget_report"))
async def retarget_report_command(message: Message, command: CommandObject, db: Database, settings: Settings) -> None:
    if not _is_admin(message, settings):
        return
    raw_id = (command.args or "").strip()
    try:
        broadcast_id = UUID(raw_id)
    except ValueError:
        await message.answer("Usage: <code>/retarget_report BROADCAST_UUID</code>")
        return
    try:
        report = await MarketingService(db, settings).broadcast_report(broadcast_id)
    except LookupError:
        await message.answer("⚠️ Broadcast not found.")
        return
    await message.answer(_report_text(report), reply_markup=_report_keyboard(broadcast_id))
