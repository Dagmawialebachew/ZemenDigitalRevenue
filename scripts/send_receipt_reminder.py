"""
Custom Broadcast & Receipt Screenshot Reminder Launcher
======================================================
Sends personalized, high-speed broadcasts with native in-bot action buttons.

Usage:
    python scripts/send_receipt_reminder.py
    python scripts/send_receipt_reminder.py --audience pending_proof --yes
    python scripts/send_receipt_reminder.py --custom-am "የፈለጉትን ጽሁፍ እዚህ..."
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
from html import escape
from pathlib import Path
import sys
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ButtonStyle, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.config import get_settings
from backend.db.pool import Database
from bot.keyboards.primitives import inline_action

DEFAULT_AM_COPY = (
    "<b>{first_name}፣ ሰላም 👋</b>\n\n"
    "⚠️ <b>ክፍያ ፈጽመው የከፈሉበትን ደረሰኝ (Screenshot) ያልላኩ ደንበኞች፦</b>\n\n"
    "የከፈሉበትን የTelebirr ወይም CBE ደረሰኝ/Screenshot ከታች ያለውን <b>«📸 ደረሰኝ/Screenshot አስገቡ»</b> የሚለውን ቁልፍ በመጫን ወዲያውኑ ያስገቡ።\n\n"
    "ደረሰኙ እንደደረሰን መጽሐፉን ወዲያውኑ በቴሌግራም ያገኛሉ! 👇"
)

DEFAULT_EN_COPY = (
    "<b>Hello {first_name} 👋</b>\n\n"
    "⚠️ <b>If you have already made your payment but haven't sent the receipt:</b>\n\n"
    "Please tap the <b>«📸 Upload Receipt/Screenshot»</b> button below to submit your transfer screenshot.\n\n"
    "As soon as you upload it, your complete guide will be delivered immediately! 👇"
)

DEFAULT_BUTTON_AM = "📸 ደረሰኝ/Screenshot አስገቡ"
DEFAULT_BUTTON_EN = "📸 Upload Receipt/Screenshot"


def _progress_bar(sent: int, total: int, width: int = 20) -> str:
    if total <= 0:
        return "[" + "█" * width + "] 100%"
    pct = min(1.0, max(0.0, sent / total))
    filled = int(round(pct * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {int(pct * 100)}%"


async def get_target_users(db: Database, audience_kind: str) -> list[dict[str, object]]:
    async with db.acquire() as conn:
        if audience_kind == "pending_proof":
            # Users with an open/pending order or intent who haven't had an approved payment yet
            rows = await conn.fetch(
                """
                SELECT DISTINCT u.id, u.telegram_id, u.first_name,
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
        elif audience_kind == "everyone":
            rows = await conn.fetch(
                """
                SELECT u.id, u.telegram_id, u.first_name,
                       COALESCE(u.preferred_language, 'am') AS language
                FROM users u
                WHERE u.status = 'active' AND u.is_bot_blocked = FALSE
                ORDER BY u.id
                """
            )
        else:  # all non-buyers
            rows = await conn.fetch(
                """
                SELECT u.id, u.telegram_id, u.first_name,
                       COALESCE(u.preferred_language, 'am') AS language
                FROM users u
                WHERE u.status = 'active'
                  AND u.is_bot_blocked = FALSE
                  AND NOT EXISTS (
                    SELECT 1 FROM orders o
                    WHERE o.user_id = u.id AND o.status = 'paid'
                  )
                ORDER BY u.id
                """
            )
    return [dict(r) for r in rows]


async def run_broadcast(
    *,
    audience_kind: str = "pending_proof",
    am_copy: str = DEFAULT_AM_COPY,
    en_copy: str = DEFAULT_EN_COPY,
    button_am: str = DEFAULT_BUTTON_AM,
    button_en: str = DEFAULT_BUTTON_EN,
    skip_confirm: bool = False,
) -> None:
    settings = get_settings()
    db = Database(settings)
    await db.open()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        users = await get_target_users(db, audience_kind)
        total = len(users)

        print("\n" + "=" * 60)
        print("📨 ZEMEN RECEIPT REMINDER & CUSTOM BROADCASTER")
        print("=" * 60)
        print(f"🎯 Target Audience: {audience_kind.upper()} ({total} users)")
        print("-" * 60)
        print("📝 AMHARIC PREVIEW:")
        print(am_copy.replace("{first_name}", "ዳግማዊ"))
        print(f"🔘 Button: [{button_am}] -> (Opens checkout & payment proof)")
        print("-" * 60)
        print("📝 ENGLISH PREVIEW:")
        print(en_copy.replace("{first_name}", "Dagmawi"))
        print(f"🔘 Button: [{button_en}] -> (Opens checkout & payment proof)")
        print("=" * 60)

        if total == 0:
            print("⚠️ No matching users found for this audience.")
            return

        if not skip_confirm:
            ans = input(f"\n🚀 Ready to broadcast to {total} users at 25 msgs/sec? (Type 'YES' to proceed): ").strip()
            if ans != "YES":
                print("❌ Cancelled by user.")
                return

        print(f"\n⚡️ Dispatching to {total} users concurrently...")

        builder_am = InlineKeyboardBuilder()
        builder_am.row(inline_action(text=button_am, callback_data="retarget:action:buy", style=ButtonStyle.SUCCESS))
        markup_am = builder_am.as_markup()

        builder_en = InlineKeyboardBuilder()
        builder_en.row(inline_action(text=button_en, callback_data="retarget:action:buy", style=ButtonStyle.SUCCESS))
        markup_en = builder_en.as_markup()

        sem = asyncio.Semaphore(25)  # 25 msgs/sec
        sent_count = 0
        blocked_count = 0
        failed_count = 0

        async def _send_one(u: dict[str, object]) -> None:
            nonlocal sent_count, blocked_count, failed_count
            async with sem:
                tid = int(u["telegram_id"])
                uid = u["id"]
                lang = str(u["language"] or "am")
                raw_name = str(u["first_name"] or "").strip()
                name = escape(raw_name) if raw_name else ("ውድ ደንበኛችን" if lang == "am" else "Friend")

                text = (en_copy if lang == "en" else am_copy).replace("{first_name}", name)
                markup = markup_en if lang == "en" else markup_am

                try:
                    await bot.send_message(chat_id=tid, text=text, reply_markup=markup)
                    sent_count += 1
                except TelegramForbiddenError:
                    blocked_count += 1
                    with contextlib.suppress(Exception):
                        async with db.transaction() as conn:
                            await conn.execute("UPDATE users SET is_bot_blocked = TRUE, updated_at = now() WHERE id = $1", uid)
                except TelegramRetryAfter as retry:
                    await asyncio.sleep(float(retry.retry_after))
                    try:
                        await bot.send_message(chat_id=tid, text=text, reply_markup=markup)
                        sent_count += 1
                    except Exception:
                        failed_count += 1
                except Exception:
                    failed_count += 1

                processed = sent_count + blocked_count + failed_count
                pbar = _progress_bar(processed, total)
                sys.stdout.write(f"\rProgress: {pbar} | Sent: {sent_count} | Blocked: {blocked_count} | Failed: {failed_count}")
                sys.stdout.flush()

        tasks = [_send_one(u) for u in users]
        await asyncio.gather(*tasks, return_exceptions=True)

        print("\n\n" + "=" * 60)
        print("✅ BROADCAST COMPLETE!")
        print(f"• Total Targets: {total}")
        print(f"• Delivered: {sent_count}")
        print(f"• Blocked by User: {blocked_count}")
        print(f"• Failed: {failed_count}")
        print("=" * 60 + "\n")

    finally:
        await bot.session.close()
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Zemen Custom & Receipt Reminder Broadcaster")
    parser.add_argument(
        "--audience",
        choices=["pending_proof", "non_buyers", "everyone"],
        default="pending_proof",
        help="Target audience segment (default: pending_proof)",
    )
    parser.add_argument("--custom-am", type=str, default=None, help="Custom Amharic message text")
    parser.add_argument("--custom-en", type=str, default=None, help="Custom English message text")
    parser.add_argument("--button-am", type=str, default=DEFAULT_BUTTON_AM, help="Button text for Amharic")
    parser.add_argument("--button-en", type=str, default=DEFAULT_BUTTON_EN, help="Button text for English")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt and send immediately")

    args = parser.parse_args()

    am_text = args.custom_am or DEFAULT_AM_COPY
    en_text = args.custom_en or DEFAULT_EN_COPY

    asyncio.run(
        run_broadcast(
            audience_kind=args.audience,
            am_copy=am_text,
            en_copy=en_text,
            button_am=args.button_am,
            button_en=args.button_en,
            skip_confirm=args.yes,
        )
    )


if __name__ == "__main__":
    main()
