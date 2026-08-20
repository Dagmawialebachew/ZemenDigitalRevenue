from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from bot.keyboards.home import home_keyboard
from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.products import ProductRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.users import UserRepository
from backend.services.salesman import SalesmanService
from bot.keyboards.sales import after_detail_keyboard, sales_keyboard
from bot.services.current_user import load_current_entry_context
from bot.services.sales_copy import detail_text, pitch_text

router = Router(name="sales")


async def send_product_picker(
    *,
    message: Message,
    db: Database,
    user_id: object,
) -> None:
    products_repo = ProductRepository()
    users_repo = UserRepository()

    async with db.transaction() as conn:
        user = await users_repo.get_by_id(conn, user_id=user_id)
        if user is None:
            return

        language = user["preferred_language"] or "am"

        products = await products_repo.list_active_sales_cards(
            conn,
            language=language,
        )

    if not products:
        text = (
            "📦 <b>No products are available right now.</b>\n\n"
            "Please check again soon."
            if language == "en"
            else
            "📦 <b>በአሁኑ ጊዜ የሚገኝ ምርት የለም።</b>\n\n"
            "በቅርቡ እንደገና ይመልከቱ።"
        )

        await message.answer(text)
        return

    if language == "en":
        text = (
            "🛍️ <b>Choose what you’re interested in</b>\n\n"
            "Here are the digital products currently available. "
            "Choose one below and I’ll show you the details 👇"
        )
    else:
        text = (
            "🛍️ <b>የሚፈልጉትን ይምረጡ</b>\n\n"
            "አሁን የሚገኙት የZemen Digital ምርቶች እነዚህ ናቸው። "
            "አንዱን ይምረጡ፤ ዝርዝሩን እናሳይዎታለን 👇"
        )

    rows: list[list[InlineKeyboardButton]] = []

    for product in products:
        title = str(product["title"])
        price = product["regular_price_br"]

        if price is not None:
            button_text = (
                f"📦 {title} — {price:g} Br"
                if language == "en"
                else f"📦 {title} — {price:g} ብር"
            )
        else:
            button_text = f"📦 {title}"

        rows.append(
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"sales:product:{product['id']}",
                )
            ]
        )

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def send_sales_pitch(
    *,
    message: Message,
    db: Database,
    settings: Settings,
    user_id: object,
) -> None:
    
    service = SalesmanService(db)
    presentation = await service.presentation(user_id=user_id)

    if presentation.product_id is not None:
        if await service.owns_focused_product(user_id=user_id):
            await send_owned_product_message(
                message=message,
                db=db,
                settings=settings,
                user_id=user_id,
            )
            return

    if presentation.product_id is None:
        await send_product_picker(
            message=message,
            db=db,
            user_id=user_id,
        )
        return

    price = (
        f"{presentation.regular_price_br:g}"
        if presentation.regular_price_br is not None
        else None
    )

    await message.answer(
        pitch_text(presentation),
        reply_markup=sales_keyboard(
            language=presentation.language,
            price_br=price,
        ),
    )


@router.callback_query(F.data.startswith("sales:product:"))
async def choose_sales_product(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    if callback.message is None or current is None:
        await callback.answer()
        return

    product_id = callback.data.removeprefix("sales:product:")

    products_repo = ProductRepository()
    sessions_repo = ConversationSessionRepository()

    async with db.transaction() as conn:
        product = await products_repo.get_active_by_id(
            conn,
            product_id=product_id,
        )

        if product is None:
            await callback.answer(
                "This product is no longer available.",
                show_alert=True,
            )
            return

        await sessions_repo.set_focus_product(
            conn,
            user_id=current.user_id,
            product_id=product["id"],
        )

    await callback.answer("✅")

    await send_sales_pitch(
        message=callback.message,
        db=db,
        settings=settings,
        user_id=current.user_id,
    )


@router.callback_query(F.data == "sales:continue")
async def continue_sales(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    await callback.answer()

    if callback.message is None or current is None:
        return

    if not current.profile_completed:
        from bot.routers.onboarding import send_onboarding_step

        await send_onboarding_step(
            message=callback.message,
            db=db,
            user_id=current.user_id,
        )
        return

    await send_sales_pitch(
        message=callback.message,
        db=db,
        settings=settings,
        user_id=current.user_id,
    )


@router.callback_query(F.data.in_({"sales:preview", "sales:question"}))
async def sales_detail(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    await callback.answer()

    if callback.message is None or current is None:
        return

    kind = (
        "preview"
        if callback.data == "sales:preview"
        else "objection"
    )
    
    service = SalesmanService(db)

    if await service.owns_focused_product(user_id=current.user_id):
        await send_owned_product_message(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
        )
        return

    detail = await SalesmanService(db).detail(
        user_id=current.user_id,
        kind=kind,
    )

    presentation = detail.presentation

    price = (
        f"{presentation.regular_price_br:g}"
        if presentation.regular_price_br is not None
        else None
    )

    await callback.message.answer(
        detail_text(detail, kind=kind),
        reply_markup=after_detail_keyboard(
            language=presentation.language,
            price_br=price,
        ),
    )


@router.callback_query(F.data == "sales:buy")
async def sales_buy(
    callback: CallbackQuery,
    db: Database,
    settings: Settings,
) -> None:
    current = await load_current_entry_context(
        db,
        telegram_user=callback.from_user,
    )

    await callback.answer("💚")

    if callback.message is None or current is None:
        return

    presentation = await SalesmanService(db).record_buy_click(
        user_id=current.user_id,
    )

    if presentation.product_slug is None:
        await send_product_picker(
            message=callback.message,
            db=db,
            user_id=current.user_id,
        )
        return

    from bot.routers.payments import send_checkout

    try:
        await send_checkout(
            message=callback.message,
            db=db,
            settings=settings,
            user_id=current.user_id,
            product_slug=presentation.product_slug,
        )

    except ValueError as exc:
        if str(exc) == "product already owned":
            if presentation.language == "en":
                await callback.message.answer(
                    "✅ <b>You already own this product.</b>\n\n"
                    "There’s no need to pay for it again. "
                    "Open your Library to access your purchase.",
                    reply_markup=home_keyboard(
                        mini_app_url=settings.mini_app_url,
                    ),
                )
            else:
                await callback.message.answer(
                    "✅ <b>ይህን ምርት ከዚህ በፊት ገዝተዋል።</b>\n\n"
                    "እንደገና መክፈል አያስፈልግዎትም። "
                    "የገዙትን ምርት ከLibraryዎ ይክፈቱ።",
                    reply_markup=home_keyboard(
                        mini_app_url=settings.mini_app_url,
                    ),
                )
            return

        raise


async def send_owned_product_message(
    *,
    message: Message,
    db: Database,
    settings: Settings,
    user_id: object,
) -> None:
    presentation = await SalesmanService(db).presentation(user_id=user_id)

    if presentation.language == "en":
        text = (
            "✅ <b>You already own this product.</b>\n\n"
            "There’s no need to buy it again. Open your Library to access it."
        )
    else:
        text = (
            "✅ <b>ይህን ምርት ከዚህ በፊት ገዝተዋል።</b>\n\n"
            "እንደገና መግዛት አያስፈልግዎትም። "
            "ከLibraryዎ ውስጥ የገዙትን ምርት ይክፈቱ።"
        )

    await message.answer(
        text,
        reply_markup=home_keyboard(
            mini_app_url=settings.mini_app_url,
        ),
    )