from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.db.pool import Database
from backend.domain.sales import SalesProfile, audience_keys
from backend.repositories.events import EventRepository
from backend.repositories.journeys import JourneyRepository
from backend.repositories.products import ProductRepository
from backend.repositories.sales_content import SalesContentRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.tracking import TrackingRepository
from backend.repositories.users import UserRepository
from backend.repositories.payments import PaymentRepository

@dataclass(frozen=True, slots=True)
class SalesMediaAsset:
    id: Any
    media_type: str
    storage_type: str
    value: str
    language: str | None
    alt_text: str | None
    caption: str | None
    sort_order: int
    mime_type: str | None
    file_name: str | None


@dataclass(frozen=True, slots=True)
class SalesPresentation:
    user_id: Any
    language: str
    first_name: str
    product_id: Any | None
    product_slug: str | None
    product_title: str | None
    short_description: str | None
    regular_price_br: Decimal | None
    profile: SalesProfile
    angle: str | None
    override_hook: dict[str, object] | None = None
    media: tuple[SalesMediaAsset, ...] = ()


@dataclass(frozen=True, slots=True)
class SalesDetail:
    presentation: SalesPresentation
    benefits: tuple[str, ...]
    override_content: dict[str, object] | None = None


class SalesmanService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository()
        self.sessions = ConversationSessionRepository()
        self.products = ProductRepository()
        self.tracking = TrackingRepository()
        self.events = EventRepository()
        self.journeys = JourneyRepository()
        self.content = SalesContentRepository()
        self.payments=PaymentRepository()
    
    async def owns_focused_product(self, *, user_id: Any) -> bool:
        async with self.db.transaction() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user is None:
                raise LookupError("user not found")

            session = await self.sessions.get(conn, user_id=user_id)
            if not session or not session["focus_product_id"]:
                return False

            product = await self.products.get_active_by_id(
                conn,
                product_id=session["focus_product_id"],
            )
            if product is None:
                return False

            checkout_product = await self.payments.get_product_for_checkout(
                conn,
                user_id=user_id,
                slug=product["slug"],
            )

            return bool(checkout_product and checkout_product["is_owned"])
        
    @staticmethod
    def _profile(record: Any | None) -> SalesProfile:
        if not record:
            return SalesProfile()
        return SalesProfile(
            role=record["role"],
            ai_experience=record["ai_experience"],
            main_goal=record["main_goal"],
            main_obstacle=record["main_obstacle"],
        )

    @staticmethod
    def _media(rows: list[Any]) -> tuple[SalesMediaAsset, ...]:
        return tuple(
            SalesMediaAsset(
                id=row["id"],
                media_type=str(row["media_type"]),
                storage_type=str(row["storage_type"]),
                value=str(row["value"]),
                language=row["language"],
                alt_text=row["alt_text"],
                caption=row["caption"],
                sort_order=int(row["sort_order"] or 0),
                mime_type=row["mime_type"],
                file_name=row["file_name"],
            )
            for row in rows
        )

    async def presentation(self, *, user_id: Any) -> SalesPresentation:
        async with self.db.transaction() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user is None:
                raise LookupError("user not found")
            profile_record = await self.users.get_profile(conn, user_id=user_id)
            profile = self._profile(profile_record)
            session = await self.sessions.get(conn, user_id=user_id)
            language = user["preferred_language"] or "am"
            product_card = None
            source = None
            block = None
            media: tuple[SalesMediaAsset, ...] = ()
            if session and session["focus_tracking_link_id"]:
                source = await self.tracking.get_by_id(conn, session["focus_tracking_link_id"])
            angle = source["angle"] if source else None
            if session and session["focus_product_id"]:
                product_card = await self.products.get_sales_card(
                    conn,
                    product_id=session["focus_product_id"],
                    language=language,
                )
                if product_card:
                    media = self._media(
                        await self.products.list_active_media(
                            conn,
                            product_id=session["focus_product_id"],
                            language=language,
                        )
                    )
                    block_record = await self.content.get_best_block(
                        conn,
                        product_id=session["focus_product_id"],
                        language=language,
                        block_key="sales_hook",
                        audience_keys=audience_keys(profile, angle=angle),
                    )
                    block = dict(block_record["content"]) if block_record else None
                    await self.journeys.record_unique_signal(
                        conn,
                        user_id=user_id,
                        product_id=session["focus_product_id"],
                        signal_key="SALES_PITCH_VIEWED",
                        payload={"angle": angle or ""},
                    )
                    if str(user["customer_stage"]) in {"new", "onboarding", "exploring", "product_interested"}:
                        await self.users.set_customer_stage(
                            conn, user_id=user_id, stage="product_interested"
                        )
                    await self.events.append(
                        conn,
                        event_type="SALES_PITCH_VIEWED",
                        user_id=user_id,
                        product_id=session["focus_product_id"],
                        tracking_link_id=session["focus_tracking_link_id"],
                        payload={"angle": angle},
                    )
                    await self.sessions.set_sales_step(
                        conn, user_id=user_id, step_key="sales_pitch"
                    )

            return SalesPresentation(
                user_id=user_id,
                language=language,
                first_name=user["first_name"],
                product_id=session["focus_product_id"] if session else None,
                product_slug=product_card["slug"] if product_card else None,
                product_title=product_card["title"] if product_card else None,
                short_description=product_card["short_description"] if product_card else None,
                regular_price_br=product_card["regular_price_br"] if product_card else None,
                profile=profile,
                angle=angle,
                override_hook=block,
                media=media,
            )

    async def detail(self, *, user_id: Any, kind: str = "preview") -> SalesDetail:
        async with self.db.transaction() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user is None:
                raise LookupError("user not found")
            profile_record = await self.users.get_profile(conn, user_id=user_id)
            profile = self._profile(profile_record)
            session = await self.sessions.get(conn, user_id=user_id)
            language = user["preferred_language"] or "am"
            source = None
            product_card = None
            benefits: tuple[str, ...] = ()
            override = None
            media: tuple[SalesMediaAsset, ...] = ()
            angle = None
            if session and session["focus_tracking_link_id"]:
                source = await self.tracking.get_by_id(conn, session["focus_tracking_link_id"])
                angle = source["angle"] if source else None
            if session and session["focus_product_id"]:
                product_card = await self.products.get_sales_card(
                    conn, product_id=session["focus_product_id"], language=language
                )
                translation = await self.products.get_translation(
                    conn, product_id=session["focus_product_id"], language=language
                )
                media = self._media(
                    await self.products.list_active_media(
                        conn,
                        product_id=session["focus_product_id"],
                        language=language,
                    )
                )
                if translation and translation["benefits"]:
                    raw = translation["benefits"]
                    benefits = tuple(str(x) for x in raw if x) if isinstance(raw, list) else ()
                block_record = await self.content.get_best_block(
                    conn,
                    product_id=session["focus_product_id"],
                    language=language,
                    block_key=f"sales_{kind}",
                    audience_keys=audience_keys(profile, angle=angle),
                )
                override = dict(block_record["content"]) if block_record else None
                signal_key = "PREVIEW_VIEWED" if kind == "preview" else "OBJECTION_OPENED"
                await self.journeys.record_unique_signal(
                    conn,
                    user_id=user_id,
                    product_id=session["focus_product_id"],
                    signal_key=signal_key,
                )
                await self.events.append(
                    conn,
                    event_type=signal_key,
                    user_id=user_id,
                    product_id=session["focus_product_id"],
                    tracking_link_id=session["focus_tracking_link_id"],
                    payload={"kind": kind},
                )
                await self.sessions.set_sales_step(
                    conn,
                    user_id=user_id,
                    step_key=f"sales_{kind}",
                )
            p = SalesPresentation(
                user_id=user_id,
                language=language,
                first_name=user["first_name"],
                product_id=session["focus_product_id"] if session else None,
                product_slug=product_card["slug"] if product_card else None,
                product_title=product_card["title"] if product_card else None,
                short_description=product_card["short_description"] if product_card else None,
                regular_price_br=product_card["regular_price_br"] if product_card else None,
                profile=profile,
                angle=angle,
                media=media,
            )
            return SalesDetail(presentation=p, benefits=benefits, override_content=override)

    async def record_media_action(self, *, user_id: Any, action: str) -> None:
        signals = {
            "gallery": "GALLERY_OPENED",
            "sample": "SAMPLE_PDF_OPENED",
        }
        signal_key = signals.get(action)
        if signal_key is None:
            raise ValueError("Unsupported sales media action")
        async with self.db.transaction() as conn:
            session = await self.sessions.get(conn, user_id=user_id)
            if not session or not session["focus_product_id"]:
                return
            await self.journeys.record_unique_signal(
                conn,
                user_id=user_id,
                product_id=session["focus_product_id"],
                signal_key=signal_key,
            )
            await self.events.append(
                conn,
                event_type=signal_key,
                user_id=user_id,
                product_id=session["focus_product_id"],
                tracking_link_id=session["focus_tracking_link_id"],
                payload={"surface": "bot"},
            )

    async def record_buy_click(self, *, user_id: Any) -> SalesPresentation:
        presentation = await self.presentation(user_id=user_id)
        if presentation.product_id is None:
            return presentation
        async with self.db.transaction() as conn:
            session = await self.sessions.get(conn, user_id=user_id)
            await self.journeys.record_unique_signal(
                conn,
                user_id=user_id,
                product_id=presentation.product_id,
                signal_key="BUY_CLICKED",
            )
            await self.users.set_customer_stage(conn, user_id=user_id, stage="buy_clicked")
            await self.sessions.set_sales_step(conn, user_id=user_id, step_key="buy_intent")
            await self.events.append(
                conn,
                event_type="BUY_CLICKED",
                user_id=user_id,
                product_id=presentation.product_id,
                tracking_link_id=session["focus_tracking_link_id"] if session else None,
                payload={"price_br": str(presentation.regular_price_br or "")},
            )
        return presentation
