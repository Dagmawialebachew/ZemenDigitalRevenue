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
from backend.repositories.users import UserRepository


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
    tracking_link_id: Any | None = None
    customer_stage: str = "new"
    is_owned: bool = False
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
        self.events = EventRepository()
        self.journeys = JourneyRepository()
        self.content = SalesContentRepository()

    async def owns_focused_product(self, *, user_id: Any) -> bool:
        async with self.db.acquire() as conn:
            return bool(
                await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM conversation_sessions cs
                        JOIN products p
                          ON p.id = cs.focus_product_id
                         AND p.status = 'active'
                        JOIN entitlements ent
                          ON ent.user_id = cs.user_id
                         AND ent.product_id = p.id
                         AND ent.revoked_at IS NULL
                        WHERE cs.user_id = $1
                    )
                    """,
                    user_id,
                )
            )

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

    async def _base_row(self, conn: Any, *, user_id: Any) -> Any:
        row = await conn.fetchrow(
            """
            SELECT
                u.first_name,
                COALESCE(u.preferred_language, 'am') AS language,
                u.customer_stage,
                up.role,
                up.ai_experience,
                up.main_goal,
                up.main_obstacle,
                cs.focus_product_id,
                cs.focus_tracking_link_id,
                tl.angle,
                p.slug AS product_slug,
                p.regular_price_br,
                COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                COALESCE(
                    pt.short_description,
                    fallback.short_description
                ) AS short_description,
                pt.benefits,
                EXISTS (
                    SELECT 1
                    FROM entitlements ent
                    WHERE ent.user_id = u.id
                      AND ent.product_id = cs.focus_product_id
                      AND ent.revoked_at IS NULL
                ) AS is_owned
            FROM users u
            LEFT JOIN user_profiles up ON up.user_id = u.id
            LEFT JOIN conversation_sessions cs ON cs.user_id = u.id
            LEFT JOIN tracking_links tl ON tl.id = cs.focus_tracking_link_id
            LEFT JOIN products p
              ON p.id = cs.focus_product_id
             AND p.status = 'active'
            LEFT JOIN product_translations pt
              ON pt.product_id = p.id
             AND pt.language = COALESCE(u.preferred_language, 'am')
            LEFT JOIN product_translations fallback
              ON fallback.product_id = p.id
             AND fallback.language = p.default_language
            WHERE u.id = $1
            """,
            user_id,
        )
        if row is None:
            raise LookupError("user not found")
        return row

    async def _read_presentation(
        self,
        conn: Any,
        *,
        user_id: Any,
        block_key: str,
    ) -> tuple[SalesPresentation, Any, dict[str, object] | None]:
        row = await self._base_row(conn, user_id=user_id)
        profile = self._profile(row)
        media: tuple[SalesMediaAsset, ...] = ()
        block = None
        product_id = row["focus_product_id"]
        if product_id is not None and row["product_slug"] is not None:
            media = self._media(
                await self.products.list_active_media(
                    conn,
                    product_id=product_id,
                    language=row["language"],
                )
            )
            block_record = await self.content.get_best_block(
                conn,
                product_id=product_id,
                language=row["language"],
                block_key=block_key,
                audience_keys=audience_keys(profile, angle=row["angle"]),
            )
            block = dict(block_record["content"]) if block_record else None

        return (
            SalesPresentation(
                user_id=user_id,
                language=row["language"],
                first_name=row["first_name"],
                product_id=product_id,
                product_slug=row["product_slug"],
                product_title=row["product_title"],
                short_description=row["short_description"],
                regular_price_br=row["regular_price_br"],
                profile=profile,
                angle=row["angle"],
                tracking_link_id=row["focus_tracking_link_id"],
                customer_stage=str(row["customer_stage"]),
                is_owned=bool(row["is_owned"]),
                override_hook=block if block_key == "sales_hook" else None,
                media=media,
            ),
            row,
            block,
        )

    async def presentation(self, *, user_id: Any) -> SalesPresentation:
        async with self.db.acquire() as conn:
            presentation, _, _ = await self._read_presentation(
                conn,
                user_id=user_id,
                block_key="sales_hook",
            )
            return presentation

    async def detail(self, *, user_id: Any, kind: str = "preview") -> SalesDetail:
        async with self.db.acquire() as conn:
            presentation, row, block = await self._read_presentation(
                conn,
                user_id=user_id,
                block_key=f"sales_{kind}",
            )
            benefits: tuple[str, ...] = ()
            if row["benefits"]:
                raw = row["benefits"]
                benefits = tuple(str(item) for item in raw if item) if isinstance(raw, list) else ()
            return SalesDetail(
                presentation=presentation,
                benefits=benefits,
                override_content=block,
            )

    async def record_pitch_view(self, presentation: SalesPresentation) -> None:
        if presentation.product_id is None or presentation.product_slug is None:
            return
        async with self.db.transaction() as conn:
            await self.journeys.record_unique_signal(
                conn,
                user_id=presentation.user_id,
                product_id=presentation.product_id,
                signal_key="SALES_PITCH_VIEWED",
                payload={"angle": presentation.angle or ""},
            )
            if presentation.customer_stage in {
                "new",
                "onboarding",
                "exploring",
                "product_interested",
            }:
                await self.users.set_customer_stage(
                    conn,
                    user_id=presentation.user_id,
                    stage="product_interested",
                )
            await self.events.append(
                conn,
                event_type="SALES_PITCH_VIEWED",
                user_id=presentation.user_id,
                product_id=presentation.product_id,
                tracking_link_id=presentation.tracking_link_id,
                payload={"angle": presentation.angle},
            )
            await self.sessions.set_sales_step(
                conn,
                user_id=presentation.user_id,
                step_key="sales_pitch",
            )

    async def record_detail_view(self, detail: SalesDetail, *, kind: str) -> None:
        presentation = detail.presentation
        if presentation.product_id is None or presentation.product_slug is None:
            return
        signal_key = "PREVIEW_VIEWED" if kind == "preview" else "OBJECTION_OPENED"
        async with self.db.transaction() as conn:
            await self.journeys.record_unique_signal(
                conn,
                user_id=presentation.user_id,
                product_id=presentation.product_id,
                signal_key=signal_key,
            )
            await self.events.append(
                conn,
                event_type=signal_key,
                user_id=presentation.user_id,
                product_id=presentation.product_id,
                tracking_link_id=presentation.tracking_link_id,
                payload={"kind": kind},
            )
            await self.sessions.set_sales_step(
                conn,
                user_id=presentation.user_id,
                step_key=f"sales_{kind}",
            )

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
