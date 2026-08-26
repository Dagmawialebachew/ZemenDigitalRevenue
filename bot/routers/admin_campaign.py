from __future__ import annotations

from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from backend.core.config import Settings
from backend.db.pool import Database
from backend.services.marketing import MarketingService


router = Router(name="admin_campaign")

_ADMIN_CAMPAIGN_SESSIONS: dict[int, dict[str, Any]] = {}


def _admin_keyboard(has_photo: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    if has_photo:
        buttons.append([
            InlineKeyboardButton(text="🚀 Confirm & Launch (4 Stages)", callback_data="admin:camp:confirm"),
        ])
        buttons.append([
            InlineKeyboardButton(text="📄 Launch Text-Only", callback_data="admin:camp:launch:none"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:camp:cancel"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="📄 Launch Text-Only", callback_data="admin:camp:launch:none"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:camp:cancel"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("campaign", "recovery", "broadcast299"))
async def start_admin_campaign(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return

    svc = MarketingService(db, settings, message.bot)
    try:
        preview = await svc.preview_recovery_campaign()
    except Exception as exc:
        await message.answer(f"❌ Could not load campaign preview: <code>{escape(str(exc))}</code>")
        return

    _ADMIN_CAMPAIGN_SESSIONS[message.from_user.id] = {
        "product_id": preview["product"]["id"],
        "target_price_br": "299.00",
        "media_file_id": None,
        "media_type": "photo",
        "stage": "waiting_photo",
    }

    text = (
        "⚡ <b>ZEMEN RECOVERY CAMPAIGN STUDIO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Product:</b> {escape(preview['product']['title'])} (<s>{preview['product']['regular_price_br']} Br</s> ➜ <b>299 Br</b>)\n"
        "👥 <b>Reachable Audience:</b>\n"
        f"   • <b>{preview['audience']['non_buyers_count']}</b> Non-Buyers\n"
        f"   • <b>{preview['audience']['high_intent_count']}</b> High-Intent Leads\n"
        f"⏰ <b>Deadline:</b> Midnight EAT ({preview['deadline']['hours_remaining']}h left)\n\n"
        "📷 <b>Send or forward a promo photo</b> to attach to the broadcasts, or tap below to send text-only:"
    )

    await message.answer(text, reply_markup=_admin_keyboard(has_photo=False))


@router.message(F.photo)
async def receive_campaign_photo(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None or message.from_user.id not in settings.admin_telegram_ids:
        return

    session = _ADMIN_CAMPAIGN_SESSIONS.get(message.from_user.id)
    if not session or session.get("stage") != "waiting_photo":
        return

    photo = message.photo[-1]
    photo_file_id = photo.file_id
    session["media_file_id"] = photo_file_id
    session["media_type"] = "photo"
    session["stage"] = "ready_to_launch"

    svc = MarketingService(db, settings, message.bot)
    try:
        preview = await svc.preview_recovery_campaign()
        stage1 = preview["stages"][0] if preview.get("stages") else None
    except Exception:
        stage1 = None

    caption = (
        "👀 <b>PREVIEW: Blast 1A (High Intent · NOW)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{stage1['text_am'] if stage1 else ''}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 <i>Ready to launch 4-stage automated drip?</i>"
    )

    await message.answer_photo(
        photo=photo_file_id,
        caption=caption[:1024],
        reply_markup=_admin_keyboard(has_photo=True),
    )


@router.callback_query(F.data == "admin:camp:confirm")
async def confirm_admin_campaign(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Unauthorized", show_alert=True)
        return

    session = _ADMIN_CAMPAIGN_SESSIONS.pop(callback.from_user.id, {})
    await callback.answer("Launching campaign…")
    svc = MarketingService(db, settings, callback.bot)

    try:
        res = await svc.launch_full_recovery_campaign(
            admin_telegram_id=callback.from_user.id,
            data={
                "product_id": session.get("product_id"),
                "media_file_id": session.get("media_file_id"),
                "media_type": session.get("media_type", "photo"),
                "target_price_br": session.get("target_price_br", "299.00"),
            },
        )
    except Exception as exc:
        if callback.message:
            await callback.message.answer(f"❌ Campaign launch failed: <code>{escape(str(exc))}</code>")
        return

    summary_text = (
        "🚀 <b>RECOVERY CAMPAIGN LAUNCHED!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>{res['offers_created']} Customer Offers Created</b> at 299 Br\n"
        "✅ <b>4 Broadcasts Queued & Scheduled</b>\n"
        "   • Blast 1A: <b>NOW</b>\n"
        "   • Blast 1B: <b>+5 min</b>\n"
        "   • Blast 2: <b>8:00 PM</b>\n"
        "   • Blast 3: <b>11:00 PM (Final)</b>\n"
        f"🔗 <b>Tracking Link:</b> {res['tracking_url']}\n"
        "⏰ <b>Expires:</b> Midnight EAT"
    )

    if callback.message:
        await callback.message.answer(summary_text)


@router.callback_query(F.data == "admin:camp:launch:none")
async def launch_text_only_campaign(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    if callback.from_user.id not in settings.admin_telegram_ids:
        await callback.answer("Unauthorized", show_alert=True)
        return

    session = _ADMIN_CAMPAIGN_SESSIONS.pop(callback.from_user.id, {})
    await callback.answer("Launching text-only campaign…")
    svc = MarketingService(db, settings, callback.bot)

    try:
        res = await svc.launch_full_recovery_campaign(
            admin_telegram_id=callback.from_user.id,
            data={
                "product_id": session.get("product_id"),
                "media_file_id": None,
                "target_price_br": session.get("target_price_br", "299.00"),
            },
        )
    except Exception as exc:
        if callback.message:
            await callback.message.answer(f"❌ Campaign launch failed: <code>{escape(str(exc))}</code>")
        return

    summary_text = (
        "🚀 <b>RECOVERY CAMPAIGN LAUNCHED (TEXT-ONLY)!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>{res['offers_created']} Customer Offers Created</b> at 299 Br\n"
        "✅ <b>4 Broadcasts Queued & Scheduled</b>\n"
        f"🔗 <b>Tracking Link:</b> {res['tracking_url']}\n"
        "⏰ <b>Expires:</b> Midnight EAT"
    )

    if callback.message:
        await callback.message.answer(summary_text)


@router.callback_query(F.data == "admin:camp:cancel")
async def cancel_admin_campaign(
    callback: CallbackQuery,
) -> None:
    _ADMIN_CAMPAIGN_SESSIONS.pop(callback.from_user.id, None)
    await callback.answer("Cancelled")
    if callback.message:
        await callback.message.answer("❌ Campaign studio closed.")
