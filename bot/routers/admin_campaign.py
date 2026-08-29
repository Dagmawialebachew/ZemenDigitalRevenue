from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
import secrets
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.marketing import Audience, normalize_audience
from backend.repositories.events import EventRepository
from backend.repositories.marketing import MarketingRepository
from backend.repositories.products import ProductRepository
from backend.services.marketing import MarketingService
from bot.keyboards.admin_campaign import (
    discount_control_card_keyboard,
    discount_preview_cta_keyboard,
    reminder_control_card_keyboard,
    reminder_preview_cta_keyboard,
)
from bot.keyboards.primitives import inline_action

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


def _get_campaign_copy(*, price: int | Decimal, regular_price: int | Decimal) -> tuple[str, str]:
    p = str(int(price) if price % 1 == 0 else price)
    reg = str(int(regular_price) if regular_price % 1 == 0 else regular_price)

    am = (
        "<b>{first_name}፣ ዛሬ ልዩ ነገር አለዎት! 🚨👇</b>\n\n"
        "በዚህ ሳምንት ብቻ <b>52+ ሰዎች</b> «AI ከዜሮ» መመሪያን ገዝተው ስራቸውን እያቀለሉ ነው። 💡\n\n"
        f"⏳ <b>ዛሬ ብቻ — {p} ብር!</b> (ከ{reg} ብር በ-45% ቅናሽ)\n\n"
        "🎯 <b>በውስጡ ምን ያገኛሉ?</b>\n"
        "• 129 ገጽ ሙሉ በሙሉ በአማርኛ የተዘጋጀ ተግባራዊ መመሪያ 📘\n"
        "• 27+ ዝግጁ የሆኑ Copy-Paste Prompts ⚡️\n"
        "• ለቢሮ፣ ለሪፖርቶች፣ ለCVና ለንግድ ሽያጭ የተዘጋጁ AI Workflows 💼\n"
        "• በስልክዎ ብቻ የሚተገበር፤ ምንም Coding አይጠይቅም 📱\n\n"
        f"⏰ ይህ የ{p} ብር ልዩ ዋጋ <b>ዛሬ ማታ 6 ሰአት ላይ ያበቃል!</b> ከዚያ በኋላ ወደ {reg} ብር ይመለሳል።\n\n"
        "ጥያቄው ቀላል ነው፦ <b>ይቀራሉ ወይስ ይቀላቀላሉ?</b> 👇"
    )

    en = (
        "<b>{first_name}, special opportunity for you today! 🚨👇</b>\n\n"
        "<b>52+ professionals & business owners</b> bought “AI From Zero” this week to supercharge their work! 💡\n\n"
        f"⏳ <b>TODAY ONLY — {p} Br!</b> (Save 45% off the {reg} Br regular price)\n\n"
        "🎯 <b>What's included inside?</b>\n"
        "• Complete 129-page practical AI guide 📘\n"
        "• 27+ ready-to-use copy-paste prompts ⚡️\n"
        "• Step-by-step AI workflows for work, career & business 💼\n"
        "• 100% mobile-friendly — zero coding needed 📱\n\n"
        f"⏰ This {p} Br flash price <b>EXPIRES tonight at midnight!</b> After that, it returns to {reg} Br.\n\n"
        "<b>Join now before the price changes</b> 👇"
    )
    return am, en


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

    first_name = callback.from_user.first_name or "ውድ ደንበኛችን"
    regular_price = Decimal(str(ctx["regular_price_br"]))
    am_copy, _ = _get_campaign_copy(price=price, regular_price=regular_price)
    rendered_text = (
        "<b>[PREVIEW — EXACT RECIPIENT MESSAGE]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        + am_copy.replace("{first_name}", escape(first_name))
    )

    cta_keyboard = discount_preview_cta_keyboard(
        price_br=int(price) if price % 1 == 0 else price,
    )

    if callback.message:
        await callback.message.answer(rendered_text, reply_markup=cta_keyboard)
    await callback.answer("✅ Preview sent above ⬆️", show_alert=False)


async def _direct_fast_dispatcher(
    bot: Bot,
    chat_id: int,
    message_id: int,
    broadcast_id: UUID,
    db: Database,
    price: Decimal,
    regular_price: Decimal,
) -> None:
    """Dispatches messages directly and concurrently at 25 msgs/sec while updating progress live."""
    am_template, en_template = _get_campaign_copy(price=price, regular_price=regular_price)
    price_display = int(price) if price % 1 == 0 else price

    cta_builder = InlineKeyboardBuilder()
    cta_builder.row(
        inline_action(
            text=f"🔥 አሁን ይግዙ — {price_display} ብር",
            callback_data="retarget:action:buy",
            style=ButtonStyle.SUCCESS,
        )
    )
    markup = cta_builder.as_markup()

    async with db.acquire() as conn:
        recipients = await conn.fetch(
            """
            SELECT br.user_id, u.telegram_id, u.first_name, u.is_bot_blocked,
                   COALESCE(u.preferred_language, 'am') AS language
            FROM broadcast_recipients br
            JOIN users u ON u.id = br.user_id
            WHERE br.broadcast_id = $1 AND br.status = 'queued'
            """,
            broadcast_id,
        )

    total = len(recipients)
    if total == 0:
        with contextlib.suppress(Exception):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="✅ <b>All non-buyers have already received this campaign!</b>",
            )
        return

    sent_count = 0
    blocked_count = 0
    failed_count = 0
    last_ui_update = asyncio.get_event_loop().time()

    sem = asyncio.Semaphore(25)  # Safe high concurrency within Telegram limits

    async def _send_one(r: dict[str, object]) -> None:
        nonlocal sent_count, blocked_count, failed_count, last_ui_update
        async with sem:
            telegram_id = int(r["telegram_id"])
            user_id = r["user_id"]
            lang = str(r["language"] or "am")
            raw_name = str(r["first_name"] or "").strip()
            name_clean = escape(raw_name) if raw_name else ("ውድ ደንበኛችን" if lang == "am" else "Friend")

            tpl = en_template if lang == "en" else am_template
            msg_text = tpl.replace("{first_name}", name_clean)

            try:
                msg = await bot.send_message(chat_id=telegram_id, text=msg_text, reply_markup=markup)
                async with db.transaction() as conn:
                    await conn.execute(
                        "UPDATE broadcast_recipients SET status='sent', sent_at=now(), telegram_message_id=$3, updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",
                        broadcast_id, user_id, msg.message_id,
                    )
                sent_count += 1
            except TelegramForbiddenError:
                async with db.transaction() as conn:
                    await conn.execute("UPDATE users SET is_bot_blocked=TRUE, updated_at=now() WHERE id=$1", user_id)
                    await conn.execute(
                        "UPDATE broadcast_recipients SET status='blocked', last_error='bot blocked', updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",
                        broadcast_id, user_id,
                    )
                blocked_count += 1
            except TelegramRetryAfter as retry:
                await asyncio.sleep(float(retry.retry_after))
                try:
                    msg = await bot.send_message(chat_id=telegram_id, text=msg_text, reply_markup=markup)
                    async with db.transaction() as conn:
                        await conn.execute(
                            "UPDATE broadcast_recipients SET status='sent', sent_at=now(), telegram_message_id=$3, updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",
                            broadcast_id, user_id, msg.message_id,
                        )
                    sent_count += 1
                except Exception:
                    failed_count += 1
            except Exception as exc:
                async with db.transaction() as conn:
                    await conn.execute(
                        "UPDATE broadcast_recipients SET status='failed', last_error=$3, updated_at=now() WHERE broadcast_id=$1 AND user_id=$2",
                        broadcast_id, user_id, str(exc)[:500],
                    )
                failed_count += 1

            # Throttle UI edits to once every 1.5 seconds
            now = asyncio.get_event_loop().time()
            if now - last_ui_update >= 1.5:
                last_ui_update = now
                processed = sent_count + blocked_count + failed_count
                remaining = max(0, total - processed)
                p_bar = _progress_bar(processed, total)
                ui_text = (
                    f"<b>BROADCAST DISPATCH CONTROL</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 <b>Campaign:</b> {price_display} Br Flash Recovery\n"
                    f"👥 <b>Total Target:</b> {total} recipients\n\n"
                    f"<b>Status:</b> <code>🚀 DISPATCHING (FAST)</code>\n"
                    f"<b>Progress:</b> {p_bar}\n\n"
                    f"  • ✅ <b>Sent:</b> {sent_count}\n"
                    f"  • 🚫 <b>Bot Blocked:</b> {blocked_count}\n"
                    f"  • ⚠️ <b>Failed:</b> {failed_count}\n"
                    f"  • ⏳ <b>Remaining:</b> {remaining}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                    f"<i>⚡️ High-speed direct delivery in progress...</i>"
                )
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=ui_text)
                except Exception:
                    pass

    # Launch all concurrent tasks
    tasks = [_send_one(r) for r in recipients]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Mark broadcast as sent
    async with db.transaction() as conn:
        await conn.execute(
            "UPDATE broadcasts SET status='sent', completed_at=now(), updated_at=now() WHERE id=$1",
            broadcast_id,
        )

    p_bar_final = _progress_bar(sent_count + blocked_count + failed_count, total)
    final_text = (
        f"<b>BROADCAST DISPATCH CONTROL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Campaign:</b> {price_display} Br Flash Recovery\n"
        f"👥 <b>Total Target:</b> {total} recipients\n\n"
        f"<b>Status:</b> <code>✅ COMPLETED</code>\n"
        f"<b>Progress:</b> {p_bar_final}\n\n"
        f"  • ✅ <b>Delivered:</b> {sent_count}\n"
        f"  • 🚫 <b>Bot Blocked:</b> {blocked_count}\n"
        f"  • ⚠️ <b>Failed:</b> {failed_count}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎉 <b>Flash campaign sent to all recipients!</b>"
    )
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text)
    except Exception:
        pass


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

    await callback.answer("🚀 Starting fast one-time broadcast...", show_alert=False)

    marketing = MarketingService(db, settings, bot=bot)
    repo = MarketingRepository()

    async with db.transaction() as conn:
        product = await conn.fetchrow(
            """
            SELECT p.id, p.slug, p.regular_price_br, p.recovery_price_br, p.discounts_enabled,
                   COALESCE(am.title, en.title, p.slug) AS title
            FROM products p
            LEFT JOIN product_translations am ON am.product_id = p.id AND am.language = 'am'
            LEFT JOIN product_translations en ON en.product_id = p.id AND en.language = 'en'
            WHERE p.slug = $1 FOR UPDATE OF p
            """,
            slug,
        )
        if product is None:
            await callback.message.edit_text("❌ Product not found.")
            return

        prod_id = product["id"]
        if not product["discounts_enabled"]:
            await conn.execute("UPDATE products SET discounts_enabled=TRUE, updated_at=now() WHERE id=$1", prod_id)

        admin_id = await repo.admin_id(conn, callback.from_user.id)
        original_price = Decimal(str(product["regular_price_br"]))
        offer_price = price
        expires_at = datetime.now(UTC) + timedelta(seconds=86400)

        # 1. Create discount rule
        rule_row = await conn.fetchrow(
            """
            INSERT INTO discount_rules(
                product_id, name, rule_type, target_price_br, eligibility_delay_seconds,
                expires_after_seconds, is_active, created_by_admin_id, require_no_pending_payment,
                minimum_intent_score, metadata
            )
            VALUES($1, $2, 'campaign', $3, 0, 86400, TRUE, $4, TRUE, 0, '{"commissionable": false, "source": "flash_commander"}'::jsonb)
            RETURNING *
            """,
            prod_id,
            f"Flash Deal {int(offer_price)} Br ({slug})",
            offer_price,
            admin_id,
        )
        rule_id = rule_row["id"]

        # 2. Bulk create customer offers
        offers_created = await repo.bulk_create_campaign_offers(
            conn,
            discount_rule_id=rule_id,
            product_id=prod_id,
            original_price_br=original_price,
            offer_price_br=offer_price,
            expires_at=expires_at,
        )

        # 3. Create ONE unified broadcast for non-buyers
        am_copy, en_copy = _get_campaign_copy(price=offer_price, regular_price=original_price)
        bc_row = await conn.fetchrow(
            """
            INSERT INTO broadcasts(
                name, audience_definition, content_am, content_en,
                attribution_window_hours, status, started_at, created_by_admin_id
            )
            VALUES($1, $2::jsonb, $3::jsonb, $4::jsonb, 48, 'sending', now(), $5)
            RETURNING *
            """,
            f"Flash Discount {int(offer_price)} Br — {slug}",
            {"kind": "non_buyers", "product_id": str(prod_id)},
            {"text": am_copy, "buttons": [{"key": "buy", "text": f"🔥 አሁን ይግዙ — {int(offer_price)} ብር", "callback_data": "retarget:action:buy"}]},
            {"text": en_copy, "buttons": [{"key": "buy", "text": f"🔥 Get It Now — {int(offer_price)} Br", "callback_data": "retarget:action:buy"}]},
            admin_id,
        )
        broadcast_id = bc_row["id"]

        # Snapshot non-buyers
        audience = Audience(kind="non_buyers", product_id=str(prod_id))
        total_recipients = await repo.snapshot_broadcast_audience(conn, broadcast_id=broadcast_id, audience=audience)

    price_display = int(price) if price % 1 == 0 else price
    initial_text = (
        f"<b>BROADCAST DISPATCH CONTROL</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Campaign:</b> {price_display} Br Flash Recovery\n"
        f"👥 <b>Total Target:</b> {total_recipients} recipients\n"
        f"🏷 <b>Offers Created:</b> {offers_created}\n\n"
        f"<b>Status:</b> <code>🚀 DISPATCHING (FAST)</code>\n"
        f"<b>Progress:</b> [░░░░░░░░░░] 0%\n\n"
        f"  • ✅ <b>Sent:</b> 0\n"
        f"  • 🚫 <b>Bot Blocked:</b> 0\n"
        f"  • ⏳ <b>Remaining:</b> {total_recipients}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡️ Launching fast direct delivery...</i>"
    )

    await callback.message.edit_text(initial_text)

    # Spawn direct fast dispatcher task in background
    asyncio.create_task(
        _direct_fast_dispatcher(
            bot=bot,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            broadcast_id=broadcast_id,
            db=db,
            price=price,
            regular_price=original_price,
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


# ──────────────────────────  /REMIND COMMANDER  ──────────────────────────

def _get_reminder_copy() -> tuple[str, str]:
    am = (
        "<b>{first_name}፣ ሰላም 👋</b>\n\n"
        "⚠️ <b>ክፍያ ፈጽመው የከፈሉበትን ደረሰኝ (Screenshot) ያልላኩ ደንበኞች፦</b>\n\n"
        "የከፈሉበትን የTelebirr ወይም CBE ደረሰኝ/Screenshot ከታች ያለውን <b>«📸 ደረሰኝ/Screenshot አስገቡ»</b> የሚለውን ቁልፍ በመጫን ወዲያውኑ ያስገቡ።\n\n"
        "ደረሰኙ እንደደረሰን መጽሐፉን ወዲያውኑ በቴሌግራም ያገኛሉ! 👇"
    )
    en = (
        "<b>Hello {first_name} 👋</b>\n\n"
        "⚠️ <b>If you have already made your payment but haven't sent the receipt:</b>\n\n"
        "Please tap the <b>«📸 Upload Receipt/Screenshot»</b> button below to submit your transfer screenshot.\n\n"
        "As soon as you upload it, your complete guide will be delivered immediately! 👇"
    )
    return am, en


@router.message(Command("remind"))
@router.message(Command("reminder"))
async def remind_command_handler(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if not message.from_user or not _is_admin(message.from_user.id, settings):
        return

    async with db.acquire() as conn:
        count = int(
            await conn.fetchval(
                """
                SELECT count(DISTINCT u.id)
                FROM users u
                WHERE u.status = 'active'
                  AND u.is_bot_blocked = FALSE
                  AND (
                    EXISTS (
                      SELECT 1 FROM orders o
                      WHERE o.user_id = u.id AND o.status IN ('created', 'awaiting_payment', 'proof_submitted', 'under_review')
                    )
                    OR EXISTS (
                      SELECT 1 FROM user_product_journeys j
                      WHERE j.user_id = u.id AND j.stage IN ('high_intent', 'checkout_started', 'proof_uploaded')
                    )
                    OR EXISTS (
                      SELECT 1 FROM payments p
                      WHERE p.user_id = u.id AND p.status IN ('awaiting_proof', 'pending_review', 'rejected')
                    )
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM orders o
                    WHERE o.user_id = u.id AND o.status = 'paid'
                  )
                """
            )
            or 0
        )

    card_text = (
        "📸 <b>RECEIPT REMINDER COMMANDER (/remind)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Target Audience:</b> <b>{count}</b> buyers awaiting proof\n"
        "🏷 <b>Filter:</b> Initiated checkout / payment without approved receipt\n\n"
        "📝 <b>Message Angle:</b>\n"
        "<i>«ክፍያ ፈጽመው ደረሰኝ ያልላኩ ደንበኞች ከታች ያለውን ቁልፍ በመጫን ያስገቡ...»</i>\n\n"
        "🔘 <b>Action Button:</b> <code>[ 📸 ደረሰኝ/Screenshot አስገቡ ]</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Select an action to proceed:"
    )

    await message.answer(card_text, reply_markup=reminder_control_card_keyboard())


@router.callback_query(F.data == "admin:remind:preview")
async def preview_reminder_callback(
    callback: CallbackQuery,
    settings: Settings,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    first_name = callback.from_user.first_name or "ውድ ደንበኛችን"
    am_copy, _ = _get_reminder_copy()
    rendered = (
        "<b>[PREVIEW — RECEIPT REMINDER MESSAGE]</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        + am_copy.replace("{first_name}", escape(first_name))
    )

    if callback.message:
        await callback.message.answer(rendered, reply_markup=reminder_preview_cta_keyboard())
    await callback.answer("✅ Preview sent above ⬆️", show_alert=False)


async def _direct_fast_reminder_dispatcher(
    bot: Bot,
    chat_id: int,
    message_id: int,
    db: Database,
    recipients: list[dict[str, object]],
) -> None:
    am_template, en_template = _get_reminder_copy()
    markup = reminder_preview_cta_keyboard()
    total = len(recipients)

    sent_count = 0
    blocked_count = 0
    failed_count = 0
    last_ui_update = asyncio.get_event_loop().time()
    sem = asyncio.Semaphore(25)

    async def _send_one(r: dict[str, object]) -> None:
        nonlocal sent_count, blocked_count, failed_count, last_ui_update
        async with sem:
            telegram_id = int(r["telegram_id"])
            user_id = r["user_id"]
            lang = str(r["language"] or "am")
            raw_name = str(r["first_name"] or "").strip()
            name_clean = escape(raw_name) if raw_name else ("ውድ ደንበኛችን" if lang == "am" else "Friend")

            tpl = en_template if lang == "en" else am_template
            msg_text = tpl.replace("{first_name}", name_clean)

            try:
                await bot.send_message(chat_id=telegram_id, text=msg_text, reply_markup=markup)
                sent_count += 1
            except TelegramForbiddenError:
                blocked_count += 1
                with contextlib.suppress(Exception):
                    async with db.transaction() as conn:
                        await conn.execute("UPDATE users SET is_bot_blocked = TRUE, updated_at = now() WHERE id = $1", user_id)
            except TelegramRetryAfter as retry:
                await asyncio.sleep(float(retry.retry_after))
                try:
                    await bot.send_message(chat_id=telegram_id, text=msg_text, reply_markup=markup)
                    sent_count += 1
                except Exception:
                    failed_count += 1
            except Exception:
                failed_count += 1

            now = asyncio.get_event_loop().time()
            if now - last_ui_update >= 1.5:
                last_ui_update = now
                processed = sent_count + blocked_count + failed_count
                p_bar = _progress_bar(processed, total)
                ui_text = (
                    "<b>RECEIPT REMINDER DISPATCH</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👥 <b>Total Target:</b> {total} pending-proof buyers\n\n"
                    "<b>Status:</b> <code>🚀 DISPATCHING (FAST)</code>\n"
                    f"<b>Progress:</b> {p_bar}\n\n"
                    f"  • ✅ <b>Sent:</b> {sent_count}\n"
                    f"  • 🚫 <b>Bot Blocked:</b> {blocked_count}\n"
                    f"  • ⚠️ <b>Failed:</b> {failed_count}\n"
                    f"  • ⏳ <b>Remaining:</b> {max(0, total - processed)}\n"
                    "━━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>⚡️ High-speed direct delivery in progress...</i>"
                )
                try:
                    await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=ui_text)
                except Exception:
                    pass

    tasks = [_send_one(r) for r in recipients]
    await asyncio.gather(*tasks, return_exceptions=True)

    p_bar_final = _progress_bar(sent_count + blocked_count + failed_count, total)
    final_text = (
        "<b>RECEIPT REMINDER DISPATCH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Target:</b> {total} pending-proof buyers\n\n"
        "<b>Status:</b> <code>✅ COMPLETED</code>\n"
        f"<b>Progress:</b> {p_bar_final}\n\n"
        f"  • ✅ <b>Delivered:</b> {sent_count}\n"
        f"  • 🚫 <b>Bot Blocked:</b> {blocked_count}\n"
        f"  • ⚠️ <b>Failed:</b> {failed_count}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎉 <b>Receipt upload reminder sent to all pending buyers!</b>"
    )
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=final_text)
    except Exception:
        pass


@router.callback_query(F.data == "admin:remind:launch")
async def launch_reminder_callback(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
    bot: Bot,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    if callback.message is None:
        await callback.answer("Session expired", show_alert=True)
        return

    await callback.answer("🚀 Launching receipt reminder broadcast...", show_alert=False)

    async with db.acquire() as conn:
        recipients = await conn.fetch(
            """
            SELECT DISTINCT u.id AS user_id, u.telegram_id, u.first_name, u.is_bot_blocked,
                   COALESCE(u.preferred_language, 'am') AS language
            FROM users u
            WHERE u.status = 'active'
              AND u.is_bot_blocked = FALSE
              AND (
                EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.user_id = u.id AND o.status IN ('created', 'awaiting_payment', 'proof_submitted', 'under_review')
                )
                OR EXISTS (
                  SELECT 1 FROM user_product_journeys j
                  WHERE j.user_id = u.id AND j.stage IN ('high_intent', 'checkout_started', 'proof_uploaded')
                )
                OR EXISTS (
                  SELECT 1 FROM payments p
                  WHERE p.user_id = u.id AND p.status IN ('awaiting_proof', 'pending_review', 'rejected')
                )
              )
              AND NOT EXISTS (
                SELECT 1 FROM orders o
                WHERE o.user_id = u.id AND o.status = 'paid'
              )
            ORDER BY u.id
            """
        )

    total = len(recipients)
    if total == 0:
        await callback.message.edit_text("ℹ️ <b>No pending-proof buyers found right now.</b>")
        return

    initial_text = (
        "<b>RECEIPT REMINDER DISPATCH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Target:</b> {total} pending-proof buyers\n\n"
        "<b>Status:</b> <code>🚀 DISPATCHING (FAST)</code>\n"
        "<b>Progress:</b> [░░░░░░░░░░] 0%\n\n"
        "  • ✅ <b>Sent:</b> 0\n"
        "  • 🚫 <b>Bot Blocked:</b> 0\n"
        f"  • ⏳ <b>Remaining:</b> {total}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>⚡️ Sending receipt upload reminders...</i>"
    )

    await callback.message.edit_text(initial_text)

    # Spawn fast dispatcher task in background
    asyncio.create_task(
        _direct_fast_reminder_dispatcher(
            bot=bot,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            db=db,
            recipients=[dict(r) for r in recipients],
        )
    )


@router.callback_query(F.data == "admin:remind:cancel")
async def cancel_reminder_callback(
    callback: CallbackQuery,
    settings: Settings,
) -> None:
    if not callback.from_user or not _is_admin(callback.from_user.id, settings):
        await callback.answer("Unauthorized", show_alert=True)
        return

    if callback.message:
        await callback.message.edit_text(
            "❌ <b>Receipt Reminder Commander Cancelled.</b>\n\n"
            "<i>No reminder messages were sent.</i>"
        )
    await callback.answer("Cancelled", show_alert=False)
