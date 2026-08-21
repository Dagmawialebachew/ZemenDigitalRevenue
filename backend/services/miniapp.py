from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape
import secrets
from typing import Any
from uuid import UUID

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.events import EventRepository
from backend.repositories.jobs import JobRepository
from backend.repositories.journeys import JourneyRepository
from backend.repositories.products import ProductRepository
from backend.repositories.referrals import ReferralRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.storefront import StorefrontRepository
from backend.repositories.tracking import TrackingRepository
from backend.repositories.users import UserRepository
from backend.security.miniapp import (
    MiniAppSessionCodec,
    TelegramMiniAppIdentity,
    validate_telegram_init_data,
)
from shared.deeplinks import StartKind, parse_start_payload
from workers.models import EnqueueJob
from backend.services.payments import PaymentService


@dataclass(frozen=True, slots=True)
class AuthenticatedMiniAppUser:
    user_id: UUID
    telegram_id: int
    first_name: str
    username: str | None
    preferred_language: str | None
    is_new_user: bool
    session_token: str
    session_expires_in: int
    focus_product_slug: str | None


class MiniAppService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.users = UserRepository()
        self.tracking = TrackingRepository()
        self.referrals = ReferralRepository()
        self.sessions = ConversationSessionRepository()
        self.products = ProductRepository()
        self.store = StorefrontRepository()
        self.events = EventRepository()
        self.journeys = JourneyRepository()

    def _codec(self) -> MiniAppSessionCodec:
        secret = self.settings.mini_app_session_secret or self.settings.bot_token
        return MiniAppSessionCodec(
            secret=secret,
            ttl_seconds=self.settings.mini_app_session_ttl_seconds,
        )

    async def authenticate_init_data(self, *, init_data: str) -> AuthenticatedMiniAppUser:
        identity = validate_telegram_init_data(
            init_data,
            bot_token=self.settings.bot_token,
            max_age_seconds=self.settings.mini_app_auth_max_age_seconds,
        )
        is_new = False
        source_name: str | None = None
        creative: str | None = None
        focus_product_id: Any | None = None
        focus_tracking_link_id: Any | None = None
        referral_attribution_id: Any | None = None

        start = parse_start_payload(identity.start_param)

        async with self.db.transaction() as conn:
            existing = await self.users.get_by_telegram_id(conn, identity.telegram_id)
            is_new = existing is None
            user = await self.users.upsert_telegram_user(
                conn,
                telegram_id=identity.telegram_id,
                username=identity.username,
                first_name=identity.first_name,
                last_name=identity.last_name,
                telegram_language_code=identity.language_code,
            )
            user_id = user["id"]
            prior_session = await self.sessions.get(conn, user_id=user_id)
            if prior_session:
                focus_product_id = prior_session["focus_product_id"]
                focus_tracking_link_id = prior_session["focus_tracking_link_id"]
                referral_attribution_id = prior_session["referral_attribution_id"]

            if start.kind == StartKind.SOURCE and start.token:
                link = await self.tracking.resolve_source_token(conn, start.token)
                if link is not None:
                    focus_product_id = link["product_id"] or focus_product_id
                    focus_tracking_link_id = link["id"]
                    source_name = link["source"]
                    creative = link["creative"]
                    await self.tracking.record_source_touch(
                        conn,
                        user_id=user_id,
                        tracking_link_id=link["id"],
                        raw_start_payload=start.raw,
                        touch_type="first" if is_new else "revisit",
                    )
            elif start.kind == StartKind.REFERRAL and start.token:
                account = await self.tracking.resolve_referral_code(conn, start.token)
                if account is not None and account["owner_user_id"] != user_id:
                    attribution = await self.referrals.create_first_touch_attribution(
                        conn,
                        referral_account_id=account["id"],
                        referrer_user_id=account["owner_user_id"],
                        referred_user_id=user_id,
                        first_product_id=focus_product_id,
                    )
                    if attribution is not None:
                        referral_attribution_id = attribution["id"]
                        await self.tracking.record_source_touch(
                            conn,
                            user_id=user_id,
                            tracking_link_id=None,
                            raw_start_payload=start.raw,
                            touch_type="referral",
                        )
            elif is_new:
                await self.tracking.record_source_touch(
                    conn,
                    user_id=user_id,
                    tracking_link_id=None,
                    raw_start_payload=start.raw,
                    touch_type="organic",
                )

            if prior_session is None:
                profile = await self.users.get_profile(conn, user_id=user_id)
                profile_completed = bool(profile and profile["onboarding_completed_at"])
                active_flow = "sales" if profile_completed else (
                    "onboarding" if user["preferred_language"] else "entry"
                )
                step_key = "resume" if profile_completed else (
                    "profile_role" if user["preferred_language"] else "language"
                )
            else:
                active_flow = prior_session["active_flow"]
                step_key = prior_session["step_key"]

            await self.sessions.upsert(
                conn,
                user_id=user_id,
                active_flow=active_flow,
                step_key=step_key,
                focus_product_id=focus_product_id,
                focus_tracking_link_id=focus_tracking_link_id,
                referral_attribution_id=referral_attribution_id,
                last_start_kind=start.kind.value,
                last_start_payload=start.raw,
                context={"miniapp_opened": True},
            )

            await self.events.append(
                conn,
                event_type="MINIAPP_OPENED",
                user_id=user_id,
                product_id=focus_product_id,
                tracking_link_id=focus_tracking_link_id,
                payload={
                    "platform": "telegram_miniapp",
                    "start_param": identity.start_param,
                    "is_premium": identity.is_premium,
                },
            )
            if is_new:
                await self.events.append(
                    conn,
                    event_type="USER_JOINED",
                    user_id=user_id,
                    product_id=focus_product_id,
                    tracking_link_id=focus_tracking_link_id,
                    payload={"source": "miniapp_direct"},
                )

            focus = await self.store.current_focus_product(conn, user_id=user_id)
            token = self._codec().issue(user_id=user_id, telegram_id=identity.telegram_id)

        if is_new:
            await self._enqueue_new_user_ops(
                identity=identity,
                user_id=user_id,
                source=source_name or "Mini App",
                creative=creative,
            )

        return AuthenticatedMiniAppUser(
            user_id=user_id,
            telegram_id=identity.telegram_id,
            first_name=user["first_name"],
            username=user["username"],
            preferred_language=user["preferred_language"],
            is_new_user=is_new,
            session_token=token,
            session_expires_in=self.settings.mini_app_session_ttl_seconds,
            focus_product_slug=focus["slug"] if focus else None,
        )

    async def _enqueue_new_user_ops(
        self,
        *,
        identity: TelegramMiniAppIdentity,
        user_id: Any,
        source: str,
        creative: str | None,
    ) -> None:
        username = f"@{escape(identity.username)}" if identity.username else "No username"
        text = (
            "🆕 <b>NEW USER</b>\n\n"
            f"👤 <b>{escape(identity.first_name or 'Telegram user')}</b> · {username}\n"
            f"🆔 <code>{identity.telegram_id}</code>\n"
            "📱 Opened Zemen Mini App\n"
            f"📣 {escape(source)} / {escape(creative or '—')}"
        )
        await JobRepository(self.db).enqueue(
            EnqueueJob(
                job_type="telegram.ops.notify",
                queue="telegram",
                job_key=f"ops:new_user:{user_id}",
                payload={"topic": "new_users", "text": text},
                max_attempts=8,
            )
        )

    async def user_from_session_token(self, token: str) -> Any:
        session = self._codec().verify(token)
        async with self.db.acquire() as conn:
            user = await self.users.get_by_id(conn, user_id=session.user_id)
        if user is None or int(user["telegram_id"]) != session.telegram_id:
            raise LookupError("Mini App user no longer exists")
        return user

    def _media_url(self, media_id: Any | None, storage_type: str | None, value: str | None) -> str | None:
        if not storage_type or not value:
            return None
        if storage_type == "url":
            return value
        if storage_type == "object_storage" and value.startswith(("https://", "http://")):
            return value
        if storage_type == "telegram_file_id" and media_id:
            path = f"/api/public/product-media/{media_id}"
            base = self.settings.public_api_base_url.rstrip("/")
            return f"{base}{path}" if base else path
        return None

    @staticmethod
    def _money(value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value.quantize(Decimal("0.01")), "f")

    def _product_summary(self, row: Any) -> dict[str, object]:
        offer_price = row["offer_price_br"]
        display_price = offer_price if offer_price is not None else row["regular_price_br"]
        return {
            "slug": row["slug"],
            "title": row["title"],
            "subtitle": row["subtitle"],
            "short_description": row["short_description"],
            "featured": bool(row["featured"]),
            "regular_price_br": self._money(row["regular_price_br"]),
            "display_price_br": self._money(display_price),
            "has_offer": offer_price is not None,
            "offer_expires_at": row["offer_expires_at"].isoformat() if row["offer_expires_at"] else None,
            "cover_url": self._media_url(row["cover_media_id"], row["cover_storage_type"], row["cover_value"]),
            "is_owned": bool(row["is_owned"]),
            "referral_enabled": bool(row["referral_enabled"]),
            "referral_commission_percent": self._money(row["referral_commission_percent"]),
        }

    async def bootstrap(self, *, user_id: Any, language: str) -> dict[str, object]:
        language = "en" if language == "en" else "am"
        async with self.db.acquire() as conn:
            user = await self.users.get_by_id(conn, user_id=user_id)
            profile = await self.users.get_profile(conn, user_id=user_id)
            rows = await self.store.list_products(
                conn, user_id=user_id, language=language, limit=30
            )
            library = await self.store.list_library(conn, user_id=user_id, language=language)
            focus = await self.store.current_focus_product(conn, user_id=user_id)
        products = [self._product_summary(row) for row in rows]
        featured = [p for p in products if p["featured"]][:4]
        if not featured:
            featured = products[:4]
        return {
            "me": {
                "first_name": user["first_name"],
                "username": user["username"],
                "language": user["preferred_language"] or language,
                "role": profile["role"] if profile else None,
                "ai_experience": profile["ai_experience"] if profile else None,
                "onboarding_complete": bool(profile and profile["onboarding_completed_at"]),
            },
            "featured": featured,
            "products": products,
            "library_count": len(library),
            "focus_product_slug": focus["slug"] if focus else None,
        }

    async def product_detail(
        self,
        *,
        user_id: Any,
        slug: str,
        language: str,
        record_view: bool = True,
    ) -> dict[str, object]:
        language = "en" if language == "en" else "am"
        async with self.db.transaction() as conn:
            row = await self.store.get_product_detail(
                conn, user_id=user_id, slug=slug, language=language
            )
            if row is None:
                raise LookupError("product not found")
            media_rows = await self.store.list_product_media(
                conn, product_id=row["id"], language=language
            )
            review_rows = await self.store.list_featured_reviews(
                conn, product_id=row["id"], language=language
            )
            if record_view:
                await self.journeys.record_unique_signal(
                    conn,
                    user_id=user_id,
                    product_id=row["id"],
                    signal_key="SALES_PITCH_VIEWED",
                    payload={"surface": "miniapp"},
                )
                await self.events.append(
                    conn,
                    event_type="PRODUCT_VIEWED",
                    user_id=user_id,
                    product_id=row["id"],
                    payload={"surface": "miniapp", "slug": slug},
                )
                await conn.execute(
                    """
                    UPDATE conversation_sessions
                    SET focus_product_id = $2,
                        active_flow = 'sales',
                        step_key = 'miniapp_product',
                        last_interaction_at = now(),
                        updated_at = now()
                    WHERE user_id = $1
                    """,
                    user_id,
                    row["id"],
                )

        offer_price = row["offer_price_br"]
        display_price = offer_price if offer_price is not None else row["regular_price_br"]
        media: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for item in media_rows:
            url = self._media_url(item["id"], item["storage_type"], item["value"])
            if not url:
                continue
            dedupe = (str(item["media_type"]), url)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            media.append(
                {
                    "type": item["media_type"],
                    "url": url,
                    "alt": item["alt_text"] or row["title"],
                    "caption": item["caption"],
                    "mime_type": item["mime_type"],
                    "file_name": item["file_name"],
                }
            )

        return {
            "slug": row["slug"],
            "title": row["title"],
            "subtitle": row["subtitle"],
            "short_description": row["short_description"],
            "description": row["description"],
            "category": row["category"],
            "benefits": list(row["benefits"] or []),
            "faq": list(row["faq"] or []),
            "regular_price_br": self._money(row["regular_price_br"]),
            "display_price_br": self._money(display_price),
            "has_offer": offer_price is not None,
            "offer_expires_at": row["offer_expires_at"].isoformat() if row["offer_expires_at"] else None,
            "is_owned": bool(row["is_owned"]),
            "referral_enabled": bool(row["referral_enabled"]),
            "referral_commission_percent": self._money(row["referral_commission_percent"]),
            "review_count": int(row["review_count"] or 0),
            "avg_rating": self._money(row["avg_rating"]),
            "media": media,
            "reviews": [
                {
                    "rating": int(review["rating"] or 0),
                    "text": review["review_text"],
                    "first_name": review["first_name"],
                }
                for review in review_rows
            ],
        }

    async def library(self, *, user_id: Any, language: str) -> list[dict[str, object]]:
        language = "en" if language == "en" else "am"
        async with self.db.transaction() as conn:
            rows = await self.store.list_library(conn, user_id=user_id, language=language)
            await self.events.append(
                conn,
                event_type="LIBRARY_OPENED",
                user_id=user_id,
                payload={"surface": "miniapp"},
            )
        return [
            {
                "slug": row["slug"],
                "title": row["title"],
                "short_description": row["short_description"],
                "delivery_status": row["delivery_status"],
                "version": row["version"],
                "granted_at": row["granted_at"].isoformat(),
                "delivered_at": row["delivered_at"].isoformat() if row["delivered_at"] else None,
                "cover_url": self._media_url(row["cover_media_id"], row["cover_storage_type"], row["cover_value"]),
                "review": ({
                    "id": str(row["review_id"]),
                    "rating": int(row["review_rating"] or 0),
                    "text": row["review_text"] or "",
                    "status": row["review_status"],
                } if row["review_id"] else None),
            }
            for row in rows
        ]

    async def referral_center(self, *, user_id: Any) -> dict[str, object]:
        async with self.db.transaction() as conn:
            account = await self.store.get_referral_account(conn, user_id=user_id)
            if account is None:
                for _ in range(8):
                    code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]
                    account = await self.store.create_referral_account(
                        conn, user_id=user_id, code=code
                    )
                    if account is not None:
                        break
                    account = await self.store.get_referral_account(conn, user_id=user_id)
                    if account is not None:
                        break
            if account is None:
                raise RuntimeError("could not create referral account")
            stats = await self.store.referral_stats(conn, user_id=user_id)
            program = await self.store.referral_program_rate(conn)
            await self.events.append(
                conn,
                event_type="REFERRAL_CENTER_OPENED",
                user_id=user_id,
                payload={"surface": "miniapp"},
            )

        link = ""
        if self.settings.bot_username:
            link = f"https://t.me/{self.settings.bot_username.lstrip('@')}?start=ref_{account['code']}"
        return {
            "code": account["code"],
            "link": link,
            "commission_percent": self._money(program["max_rate"]) or "0.00",
            "full_price_only": bool(program["full_price_only"] if program["full_price_only"] is not None else True),
            "joins": int(stats["joins"] or 0),
            "full_price_buyers": int(stats["full_price_buyers"] or 0),
            "pending_br": self._money(stats["pending_br"]),
            "available_br": self._money(stats["available_br"]),
            "paid_br": self._money(stats["paid_br"]),
        }

    async def change_language(
        self,
        *,
        user_id: Any,
        language: str,
    ) -> dict[str, str]:
        language = "en" if language == "en" else "am"
        async with self.db.transaction() as conn:
            await self.users.set_preferred_language(
                conn, user_id=user_id, language=language
            )
            await self.events.append(
                conn,
                event_type="LANGUAGE_CHANGED",
                user_id=user_id,
                payload={"surface": "miniapp", "language": language},
            )
        return {"language": language}


    async def submit_review(
        self, *, user_id: Any, slug: str, rating: int, review_text: str, language: str
    ) -> dict[str, object]:
        if rating < 1 or rating > 5:
            raise ValueError("rating must be between 1 and 5")
        text = review_text.strip()
        if len(text) < 3 or len(text) > 2000:
            raise ValueError("review must be between 3 and 2000 characters")
        language = "en" if language == "en" else "am"
        async with self.db.transaction() as conn:
            enabled = await conn.fetchval(
                "SELECT coalesce((SELECT value::text::boolean FROM settings WHERE key='reviews.prompt_enabled'),TRUE)"
            )
            if not enabled:
                raise ValueError("reviews are currently disabled")
            context = await self.store.review_purchase_context(conn,user_id=user_id,slug=slug)
            if context is None:
                raise PermissionError("only verified buyers can review this product")
            row = await self.store.submit_review(
                conn,user_id=user_id,product_id=context["product_id"],order_id=context["order_id"],
                rating=rating,review_text=text,language=language,
            )
            auto_publish = await conn.fetchval(
                "SELECT coalesce((SELECT value::text::boolean FROM settings WHERE key='reviews.auto_publish'),FALSE)"
            )
            if auto_publish and bool(row["verified_purchase"]):
                row = await conn.fetchrow(
                    "UPDATE reviews SET status='approved',moderated_at=now(),updated_at=now() WHERE id=$1 RETURNING *",
                    row["id"],
                )
            await self.events.append(
                conn,event_type="REVIEW_SUBMITTED",user_id=user_id,product_id=context["product_id"],
                order_id=context["order_id"],payload={"rating":rating,"language":language,"surface":"miniapp"},
            )
        return {"id":str(row["id"]),"status":row["status"],"rating":int(row["rating"]),"text":row["review_text"]}

    async def create_checkout(
        self,
        *,
        user_id: Any,
        slug: str,
    ) -> dict[str, object]:
        # Keep the salesperson journey signal and the financial order separate,
        # but execute both through domain services instead of browser-owned logic.
        await self.record_product_action(user_id=user_id, slug=slug, action="buy")
        checkout = await PaymentService(self.db, self.settings).create_checkout(
            user_id=user_id, product_slug=slug
        )
        chat_url = (
            f"https://t.me/{self.settings.bot_username.lstrip('@')}?start=ord_{checkout.public_id}"
            if self.settings.bot_username
            else ""
        )
        return {
            "order_public_id": checkout.public_id,
            "status": checkout.status,
            "total_due_br": f"{checkout.total_due_br:.2f}",
            "pricing_type": checkout.pricing_type,
            "discount_br": f"{checkout.discount_br:.2f}",
            "commissionable": checkout.commissionable,
            "chat_url": chat_url,
        }

    async def record_product_action(
        self,
        *,
        user_id: Any,
        slug: str,
        action: str,
    ) -> dict[str, object]:
        signal_map = {
            "preview": "PREVIEW_VIEWED",
            "buy": "BUY_CLICKED",
        }
        if action not in signal_map:
            raise ValueError("unsupported Mini App product action")
        async with self.db.transaction() as conn:
            product = await self.products.get_active_by_slug(conn, slug)
            if product is None:
                raise LookupError("product not found")
            signal = signal_map[action]
            journey = await self.journeys.record_unique_signal(
                conn,
                user_id=user_id,
                product_id=product["id"],
                signal_key=signal,
                payload={"surface": "miniapp"},
            )
            if action == "buy":
                await self.users.set_customer_stage(conn, user_id=user_id, stage="buy_clicked")
                step = "buy_intent"
            else:
                step = "sales_preview"
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET focus_product_id = $2,
                    active_flow = 'sales',
                    step_key = $3,
                    last_interaction_at = now(),
                    updated_at = now()
                WHERE user_id = $1
                """,
                user_id,
                product["id"],
                step,
            )
            await self.events.append(
                conn,
                event_type=signal,
                user_id=user_id,
                product_id=product["id"],
                payload={"surface": "miniapp"},
            )
        chat_url = (
            f"https://t.me/{self.settings.bot_username.lstrip('@')}"
            if self.settings.bot_username
            else ""
        )
        return {
            "ok": True,
            "stage": journey["stage"],
            "intent_score": int(journey["intent_score"]),
            "chat_url": chat_url,
        }
