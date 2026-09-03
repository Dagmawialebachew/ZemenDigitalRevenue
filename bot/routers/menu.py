from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from backend.core.config import Settings
from backend.db.pool import Database
from bot.keyboards.home import home_keyboard
from bot.services.current_user import load_current_entry_context

router = Router(name="menu")


def _mini_app_button(
    *,
    language: str,
    mini_app_url: str = "",
    section: str = "",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Home" if language == "en" else "🏠 ዋና ገጽ",
                    callback_data="menu:home",
                )
            ]
        ]
    )

@router.message(Command("home"))
async def home_command(
    message: Message,
    db: Database,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return

    current = await load_current_entry_context(
        db,
        telegram_user=message.from_user,
    )

    if current is None:
        await message.answer("👋 Send /start first.")
        return

    if current.language_for_copy == "en":
        text = (
            "🏠 <b>Zemen Digital</b>\n\n"
            f"Welcome back, <b>{escape(current.first_name)}</b>.\n\n"
            "What would you like to do?"
        )
    else:
        text = (
            "🏠 <b>Zemen Digital</b>\n\n"
            f"<b>{escape(current.first_name)}</b>፣ እንኳን ደህና መጡ።\n\n"
            "ምን ማድረግ ይፈልጋሉ?"
        )

    await message.answer(
        text,
        reply_markup=home_keyboard(
            mini_app_url=settings.mini_app_url,
        ),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    if current is None:
        await callback.message.answer("👋 Send /start first.")
        return

    if current.language_for_copy == "en":
        text = (
            "🏠 <b>Zemen Digital</b>\n\n"
            f"Welcome back, <b>{escape(current.first_name)}</b>.\n\n"
            "Choose what you want to do below 👇"
        )
    else:
        text = (
            "🏠 <b>Zemen Digital</b>\n\n"
            f"<b>{escape(current.first_name)}</b>፣ ከታች የሚፈልጉትን ይምረጡ 👇"
        )

    await callback.message.answer(
        text,
        reply_markup=home_keyboard(
            mini_app_url=settings.mini_app_url,
        ),
    )


@router.callback_query(F.data == "menu:library")
async def menu_library(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    if current is None:
        await callback.message.answer("👋 Send /start first.")
        return

    language = current.language_for_copy

    async with db.transaction() as conn:
        products = await conn.fetch(
            """
            SELECT
                e.id AS entitlement_id,
                e.delivery_status,
                p.id AS product_id,
                p.slug,
                COALESCE(
                    pt.title,
                    fallback.title,
                    p.slug
                ) AS title
            FROM entitlements e

            JOIN products p
              ON p.id = e.product_id

            LEFT JOIN product_translations pt
              ON pt.product_id = p.id
             AND pt.language = $2

            LEFT JOIN product_translations fallback
              ON fallback.product_id = p.id
             AND fallback.language = p.default_language

            WHERE e.user_id = $1
              AND e.revoked_at IS NULL

            ORDER BY p.created_at DESC
            """,
            current.user_id,
            language,
        )

    if not products:
        if language == "en":
            text = (
                "📚 <b>My Library</b>\n\n"
                "Your Library is currently empty.\n\n"
                "Products you purchase from Zemen Digital will appear here "
                "after your payment is approved. ✅\n\n"
                "Once a product is added to your Library, your access stays "
                "connected to your Zemen account."
            )
        else:
            text = (
                "📚 <b>የእኔ Library</b>\n\n"
                "በአሁኑ ጊዜ Libraryዎ ባዶ ነው።\n\n"
                "ከZemen Digital የሚገዙት ምርት ክፍያዎ ከተረጋገጠ ✅ "
                "በኋላ እዚህ ይጨመራል።\n\n"
                "አንድ ምርት Libraryዎ ውስጥ ከገባ በኋላ "
                "ከZemen accountዎ ጋር የተያያዘ የቋሚ መዳረሻ ይኖርዎታል።"
            )

        await callback.message.answer(
            text,
            reply_markup=_mini_app_button(
                language=language,
                mini_app_url=settings.mini_app_url,
                section="library",
            ),
        )
        return

    if language == "en":
        lines = [
            "📚 <b>My Library</b>",
            "",
            f"You currently own <b>{len(products)}</b> product"
            + ("" if len(products) == 1 else "s")
            + ".",
            "",
        ]
    else:
        lines = [
            "📚 <b>የእኔ Library</b>",
            "",
            f"በአሁኑ ጊዜ <b>{len(products)}</b> ምርት በLibraryዎ ውስጥ አለ።",
            "",
        ]

    for index, product in enumerate(products, start=1):
        title = escape(str(product["title"]))
        status = str(product["delivery_status"] or "")

        if language == "en":
            status_text = {
                "delivered": "✅ Delivered",
                "queued": "⏳ Delivery queued",
                "pending": "⏳ Preparing delivery",
                "failed": "⚠️ Delivery needs attention",
            }.get(status, "✅ Owned")

            lines.extend(
                [
                    f"<b>{index}. {title}</b>",
                    status_text,
                    "",
                ]
            )
        else:
            status_text = {
                "delivered": "✅ ደርሷል",
                "queued": "⏳ ለመላክ ተዘጋጅቷል",
                "pending": "⏳ በመዘጋጀት ላይ",
                "failed": "⚠️ መላኪያው እንደገና ማየት ያስፈልገዋል",
            }.get(status, "✅ የእርስዎ ምርት")

            lines.extend(
                [
                    f"<b>{index}. {title}</b>",
                    status_text,
                    "",
                ]
            )

    if language == "en":
        lines.extend(
            [
                "🔐 Your purchased products stay connected to your account.",
                "",
                "Open your full Library below to access your products.",
            ]
        )
    else:
        lines.extend(
            [
                "🔐 የገዙት ምርቶች ከaccountዎ ጋር ተያይዘው ይቆያሉ።",
                "",
                "ምርቶችዎን ለመክፈት ከታች Libraryዎን ይክፈቱ።",
            ]
        )

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=_mini_app_button(
            language=language,
            mini_app_url=settings.mini_app_url,
            section="library",
        ),
    )


@router.callback_query(F.data == "menu:earn")
async def menu_earn(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    await callback.answer()

    if callback.message is None:
        return

    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    if current is None:
        await callback.message.answer("👋 Send /start first.")
        return

    language = current.language_for_copy

    if language == "en":
        text = (
            "🤝 <b>Earn with Zemen</b>\n\n"
            "Share your personal Zemen referral link and earn commission "
            "from eligible purchases made through your link.\n\n"
            "💰 <b>How it works</b>\n"
            "1️⃣ Share your referral link\n"
            "2️⃣ A new customer enters through your link\n"
            "3️⃣ They purchase an eligible product at full price\n"
            "4️⃣ The payment is approved\n"
            "5️⃣ Your commission is recorded automatically\n\n"
            "⚠️ <b>Important</b>\n"
            "• Discounted or recovery-price purchases do not earn commission\n"
            "• Rejected payments do not earn commission\n"
            "• Self-referrals are not eligible\n"
            "• Your referral attribution and commission history are tracked by Zemen\n\n"
            "📊 Open Earn to see your referral link, eligible referrals "
            "and commission information."
        )
    else:
        text = (
            "🤝 <b>ከZemen ጋር ገቢ ያግኙ</b>\n\n"
            "የግል Zemen referral linkዎን በማጋራት "
            "ብቁ ከሆኑ ግዢዎች commission ማግኘት ይችላሉ።\n\n"
            "💰 <b>እንዴት ይሰራል?</b>\n"
            "1️⃣ Referral linkዎን ያጋሩ\n"
            "2️⃣ አዲስ ደንበኛ በlinkዎ ይግባ\n"
            "3️⃣ ብቁ የሆነን ምርት በመደበኛ ዋጋ ይግዛ\n"
            "4️⃣ ክፍያው ይረጋገጥ\n"
            "5️⃣ Commissionዎ በራስ-ሰር ይመዘገባል\n\n"
            "⚠️ <b>አስፈላጊ</b>\n"
            "• በDiscount ወይም Recovery Price የተደረገ ግዢ commission አያስገኝም\n"
            "• ያልተረጋገጠ ክፍያ commission አያስገኝም\n"
            "• ራስዎን referral ማድረግ አይቻልም\n"
            "• Referral እና commission historyዎ በZemen ይመዘገባል\n\n"
            "📊 Referral linkዎን፣ eligible referrals እና "
            "commission informationዎን ለማየት Earnን ይክፈቱ።"
        )

    await callback.message.answer(
        text,
        reply_markup=_mini_app_button(
            language=language,
            mini_app_url=settings.mini_app_url,
            section="earn",
        ),
    )