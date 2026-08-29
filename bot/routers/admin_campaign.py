from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from html import escape
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.products import ProductRepository
from backend.services.marketing import MarketingService
from bot.keyboards.admin_campaign import (
    discount_control_card_keyboard,
    discount_preview_cta_keyboard,
)

router = Router(name="admin_campaign")
DEFAULT_PRICE = Decimal("299.00")
DEFAULT_SLUG = "ai-kezero"


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return bool(user_id and user_id in settings.admin_telegram_ids)


def _progress_bar(sent: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "[" + "█" * width + "] 100%"
    pct = min(1.0, max(0.0, sent / total))
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {int(pct * 100)}%"


async def _get_campaign_context(
    db: Database,
    *,
    slug: str,
    price_br: Decimal,
) -> dict[str, object] | None:
    async with db.acquire() as conn:
        product = await conn.fetchrow(
            """
            SELECT p.id, p.slug, p.regular_price_br, p.recovery_price_br, p.discounts_enabled,
                   COALESCE(am.title, en.title, p.slug) AS title,
                   COALESCE(am.title, 'AI ከዜሮ') AS title_am,
                   COALESCE(en.title, 'AI From Zero') AS title_en
            FROM products p
            LEFT JOIN product_translations am ON am.product_id = p.id AND am.language = 'am'
            LEFT JOIN product_translations en ON en.product_id = p.id AND en.language = 'en'
            WHERE p.slug = $1
            """,
            slug,
        )
        if product is None:
            return None

        # Reachable non-buyers calculation:
        # active, not blocked, no paid orders for product, no in-flight payments under review
        count = int(
            await conn.fetchval(
                """
                SELECT count(DISTINCT u.id)
                FROM users u
                WHERE u.status = 'active'
                  AND u.is_bot_blocked = FALSE
                  AND NOT EXISTS (
                    SELECT 1 FROM orders o
                    JOIN order_items oi ON oi.order_id = o.id
                    WHERE o.user_id = u.id AND oi.product_id = $1 AND o.status = 'paid'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM payments p
                    WHERE p.user_id = u.id
                      AND p.status IN ('awaiting_proof', 'pending_review', 'flagged')
                  )
                """,
                product["id"],
            )
            or 0
        )

        reg_price = Decimal(str(product["regular_price_br"] or "549.00"))
        discount_pct = int(round((1 - (price_br / reg_price)) * 100)) if reg_price > 0 else 0

        cvr_3pct_sales = int(round(count * 0.03))
        cvr_5pct_sales = int(round(count * 0.05))
        cvr_10pct_sales = int(round(count * 0.10))

        return {
            "product_id": product["id"],
            "slug": product["slug"],
            "title": product["title"],
            "title_am": product["title_am"],
            "title_en": product["title_en"],
            "regular_price_br": reg_price,
            "target_price_br": price_br,
            "discount_pct": discount_pct,
            "reachable_count": count,
            "sales_3pct": cvr_3pct_sales,
            "rev_3pct": round(Decimal(cvr_3pct_sales) * price_br, 2),
            "sales_5pct": cvr_5pct_sales,
            "rev_5pct": round(Decimal(cvr_5pct_sales) * price_br, 2),
            "sales_10pct": cvr_10pct_sales,
            "rev_10pct": round(Decimal(cvr_10pct_sales) * price_br, 2),
        }


def _render_control_card(ctx: dict[str, object]) -> str:
    slug = str(ctx["slug"])
    title = escape(str(ctx["title"]))
    regular_price = int(Decimal(str(ctx["regular_price_br"])))
    price = int(Decimal(str(ctx["target_price_br"])))
    pct = int(ctx["discount_pct"])
    count = int(ctx["reachable_count"])

    sales_3 = int(ctx["sales_3pct"])
    rev_3 = float(ctx["rev_3pct"])
    sales_5 = int(ctx["sales_5pct"])
    rev_5 = float(ctx["rev_5pct"])
    sales_10 = int(ctx["sales_10pct"])
    rev_10 = float(ctx["rev_10pct"])

    return (
        "⚡️ <b>FLASH DISCOUNT COMMANDER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Product:</b> {title} (<code>{slug}</code>)\n"
        f"🏷 <b>Regular:</b> {regular_price} Br ➜ <b>Flash Deal:</b> {price} Br (-{pct}%)\n"
        f"👥 <b>Reachable Audience:</b> <b>{count}</b> non-buyers\n\n"
        "📊 <b>Projected Revenue Potential:</b>\n"
        f"  • 3% CVR ({sales_3} sales): <b>{rev_3:,.2f} Br</b>\n"
        f"  • 5% CVR ({sales_5} sales): <b>{rev_5:,.2f} Br</b>\n"
        f"  • 10% CVR ({sales_10} sales): <b>{rev_10:,.2f} Br</b> 🔥\n\n"
        "🔒 <b>Safety:</b> <code>commissionable = FALSE</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an action to proceed:"
    )


@router.message(Command("discount"))
async def discount_command_handler(
    message: Message,
    command: CommandObject,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, settings):
        return

    # Parse arguments: /discount [price] [slug]
    price = DEFAULT_PRICE
    slug = DEFAULT_SLUG

    if command.args:
        parts = command.args.strip().split()
        if len(parts) >= 1:
            try:
                price = Decimal(parts[0])
            except (InvalidOperation, ValueError):
                await message.answer("⚠️ Invalid price format. Example: <code>/discount 299 ai-kezero</code>")
                return
        if len(parts) >= 2:
            slug = parts[1].strip().lower()

    ctx = await _get_campaign_context(db, slug=slug, price_br=price)
    if ctx is None:
        await message.answer(f"❌ Product with slug <code>{slug}</code> was not found.")
        return

    card_text = _render_control_card(ctx)
    keyboard = discount_control_card_keyboard(
        price_br=int(price) if price % 1 == 0 else price,
        slug=slug,
    )
    await message.answer(card_text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin:disc:preview:"))
async def preview_discount_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        _, _, _, price_raw, slug = (callback.data or "").split(":", 4)
        price = Decimal(price_raw)
    except (ValueError, InvalidOperation):
        await callback.answer("Invalid callback data", show_alert=True)
        return

    ctx = await _get_campaign_context(db, slug=slug, price_br=price)
    if ctx is None:
        await callback.answer("Product not found", show_alert=True)
        return

    first_name = callback.from_user.first_name or "ይቅርታ"
    title_am = str(ctx["title_am"])
    regular_price = int(Decimal(str(ctx["regular_price_br"])))
    price_display = int(price) if price % 1 == 0 else price

    preview_text = (
        "<b>[PREVIEW — EXACT RECIPIENT MESSAGE]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{escape(first_name)}፣ ይህን ማወቅ አለብዎት...\n\n"
        f"በዚህ ሳምንት ብቻ 52+ ሰዎች {escape(title_am)} ገዝተዋል። ከእነሱ ጋር ለምን አልተቀላቀሉም?\n\n"
        f"ዛሬ ብቻ — {price_display} ብር (ከ{regular_price} ብር ይልቅ)\n\n"
        "ሁሉም ሰው AI እየተማረ ነው። ኢትዮጵያ ውስጥ AI ለሥራ፣ ለንግድ፣ ለትምህርት — ሁሉም እየተጠቀመ ነው።\n\n"
        "ጥያቄው ይህ ነው: ይቀራሉ ወይስ ይቀላቀላሉ?\n\n"
        "ዋጋው ዛሬ ማታ 6 ሰአት ላይ ያበቃል ⏰"
    )

    cta_keyboard = discount_preview_cta_keyboard(price_br=price_display)

    if callback.message:
        await callback.message.answer(preview_text, reply_markup=cta_keyboard)
    await callback.answer("✅ Preview sent above ⬆️", show_alert=False)


async def _poll_broadcast_progress(
    bot: Bot,
    chat_id: int,
    message_id: int,
    broadcast_ids: list[UUID],
    db: Database,
    total_recipients: int,
    campaign_name: str,
) -> None:
    """Polls database and edits Control Card every 2.5s until all broadcasts reach terminal status."""
    marketing = MarketingService(db, Settings())
    start_time = asyncio.get_event_loop().time()
    max_duration = 300  # 5 minutes safety timeout

    while asyncio.get_event_loop().time() - start_time < max_duration:
        await asyncio.sleep(2.5)

        total_sent = 0
        total_blocked = 0
        total_failed = 0
        total_queued = 0
        all_completed = True

        for b_id in broadcast_ids:
            try:
                report = await marketing.broadcast_report(b_id)
                status = str(report.get("status", ""))
                if status in {"scheduled", "sending"}:
                    all_completed = False

                sent = int(report.get("sent_count", 0))
                blocked = int(report.get("blocked_count", 0))
                failed = int(report.get("failed_count", 0))
                recipients = int(report.get("recipients", 0))
                queued = max(0, recipients - (sent + blocked + failed))

                total_sent += sent
                total_blocked += blocked
                total_failed += failed
                total_queued += queued
            except Exception:
                pass

        processed = total_sent + total_blocked + total_failed
        progress_bar = _progress_bar(processed, total_recipients)
        is_done = all_completed and total_queued == 0

        status_badge = "✅ COMPLETED" if is_done else "🚀 DISPATCHING"

        update_text = (
            f"<b>BROADCAST DISPATCH CONTROL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Campaign:</b> {escape(campaign_name)}\n"
            f"👥 <b>Total Target:</b> {total_recipients} recipients\n\n"
            f"<b>Status:</b> <code>{status_badge}</code>\n"
            f"<b>Progress:</b> {progress_bar}\n\n"
            f"  • ✅ <b>Sent:</b> {total_sent}\n"
            f"  • 🚫 <b>Bot Blocked:</b> {total_blocked}\n"
            f"  • ⚠️ <b>Failed:</b> {total_failed}\n"
            f"  • ⏳ <b>Remaining:</b> {total_queued}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>{'All messages delivered successfully! 🎉' if is_done else '⚡️ Throttled to comply with Telegram flood limits.'}</i>"
        )

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=update_text,
            )
        except TelegramBadRequest:
            pass  # Message content unchanged

        if is_done:
            break


@router.callback_query(F.data.startswith("admin:disc:launch:"))
async def launch_discount_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    try:
        _, _, _, price_raw, slug = (callback.data or "").split(":", 4)
        price = Decimal(price_raw)
    except (ValueError, InvalidOperation):
        await callback.answer("Invalid callback data", show_alert=True)
        return

    if callback.message is None:
        await callback.answer("Session expired", show_alert=True)
        return

    await callback.answer("🚀 Launching flash discount campaign...", show_alert=False)

    marketing = MarketingService(db, settings, bot=bot)
    try:
        launch_res = await marketing.launch_full_recovery_campaign(
            admin_telegram_id=callback.from_user.id,
            data={"target_price_br": str(price)},
        )
    except Exception as exc:
        await callback.message.edit_text(
            f"❌ <b>Campaign Launch Failed</b>\n\n<code>{escape(str(exc))}</code>"
        )
        return

    offers_created = launch_res.get("offers_created", 0)
    scheduled_broadcasts = launch_res.get("scheduled_broadcasts", [])
    broadcast_ids = [UUID(str(b["id"])) for b in scheduled_broadcasts if "id" in b]
    total_recipients = sum(int(b.get("recipients", 0)) for b in scheduled_broadcasts) or offers_created

    initial_text = (
        f"<b>BROADCAST DISPATCH CONTROL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Campaign:</b> {int(price) if price % 1 == 0 else price} Br Flash Recovery\n"
        f"👥 <b>Total Target:</b> {total_recipients} recipients\n"
        f"🏷 <b>Offers Created:</b> {offers_created}\n\n"
        f"<b>Status:</b> <code>🚀 DISPATCHING</code>\n"
        f"<b>Progress:</b> [░░░░░░░░░░] 0%\n\n"
        f"  • ✅ <b>Sent:</b> 0\n"
        f"  • 🚫 <b>Bot Blocked:</b> 0\n"
        f"  • ⏳ <b>Remaining:</b> {total_recipients}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡️ Initializing durable worker queue...</i>"
    )

    await callback.message.edit_text(initial_text)

    # Spawn async tracking task in background
    if broadcast_ids:
        asyncio.create_task(
            _poll_broadcast_progress(
                bot=bot,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                broadcast_ids=broadcast_ids,
                db=db,
                total_recipients=total_recipients,
                campaign_name=f"{int(price) if price % 1 == 0 else price} Br Flash Recovery",
            )
        )


@router.callback_query(F.data == "admin:disc:cancel")
async def cancel_discount_callback(
    callback: CallbackQuery,
    settings: Settings,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    if callback.message:
        await callback.message.edit_text(
            "❌ <b>Flash Discount Commander Cancelled.</b>\n\n"
            "<i>No discount rules were created and no broadcasts were dispatched.</i>"
        )
    await callback.answer("Cancelled", show_alert=False)
