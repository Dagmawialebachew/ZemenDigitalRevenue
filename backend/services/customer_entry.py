from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from aiogram.types import User as TelegramUser

from backend.db.pool import Database
from backend.domain.entry import source_touch_type
from backend.repositories.events import EventRepository
from backend.repositories.jobs import JobRepository
from backend.repositories.products import ProductRepository
from backend.repositories.referrals import ReferralRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.tracking import TrackingRepository
from backend.repositories.users import UserRepository
from shared.deeplinks import StartContext, StartKind
from workers.models import EnqueueJob


@dataclass(frozen=True, slots=True)
class CustomerEntryContext:
    user_id: Any
    telegram_id: int
    first_name: str
    username: str | None
    is_new_user: bool
    preferred_language: str | None
    profile_completed: bool
    customer_stage: str
    start_kind: StartKind
    start_token: str | None
    source_name: str | None = None
    source_platform: str | None = None
    campaign: str | None = None
    creative: str | None = None
    angle: str | None = None
    focus_product_id: Any | None = None
    focus_product_title: str | None = None
    focus_product_price_br: str | None = None
    referral_username: str | None = None
    referral_created: bool = False

    @property
    def language_for_copy(self) -> str:
        return self.preferred_language or "am"


class CustomerEntryService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.users = UserRepository()
        self.tracking = TrackingRepository()
        self.referrals = ReferralRepository()
        self.sessions = ConversationSessionRepository()
        self.products = ProductRepository()
        self.events = EventRepository()

    async def enter(self, *, telegram_user: TelegramUser, start: StartContext) -> CustomerEntryContext:
        resolved_link = None
        referral_account = None
        referral_attribution = None
        referral_created = False
        product_card = None

        async with self.db.transaction() as conn:
            existing = await self.users.get_by_telegram_id(conn, telegram_user.id)
            is_new = existing is None
            user = await self.users.upsert_telegram_user(
                conn,
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name or "",
                last_name=telegram_user.last_name,
                telegram_language_code=telegram_user.language_code,
            )
            user_id = user["id"]
            profile = await self.users.get_profile(conn, user_id=user_id)
            prior_session = await self.sessions.get(conn, user_id=user_id)

            focus_product_id = prior_session["focus_product_id"] if prior_session else None
            focus_tracking_link_id = prior_session["focus_tracking_link_id"] if prior_session else None
            referral_attribution_id = (
                prior_session["referral_attribution_id"] if prior_session else None
            )

            if start.kind == StartKind.SOURCE and start.token:
                resolved_link = await self.tracking.resolve_source_token(conn, start.token)
                if resolved_link is not None:
                    focus_product_id = resolved_link["product_id"] or focus_product_id
                    focus_tracking_link_id = resolved_link["id"]
                    await self.tracking.record_source_touch(
                        conn,
                        user_id=user_id,
                        tracking_link_id=resolved_link["id"],
                        raw_start_payload=start.raw,
                        touch_type=source_touch_type(is_new_user=is_new, resolved=True),
                    )
                else:
                    await self.tracking.record_source_touch(
                        conn,
                        user_id=user_id,
                        tracking_link_id=None,
                        raw_start_payload=start.raw,
                        touch_type=source_touch_type(is_new_user=is_new, resolved=False),
                    )

            elif start.kind == StartKind.REFERRAL and start.token:
                referral_account = await self.tracking.resolve_referral_code(conn, start.token)
                if referral_account is not None and referral_account["owner_user_id"] != user_id:
                    before = await self.referrals.get_attribution_for_user(
                        conn, referred_user_id=user_id
                    )
                    referral_attribution = await self.referrals.create_first_touch_attribution(
                        conn,
                        referral_account_id=referral_account["id"],
                        referrer_user_id=referral_account["owner_user_id"],
                        referred_user_id=user_id,
                        first_product_id=focus_product_id,
                    )
                    referral_created = before is None and referral_attribution is not None
                    if referral_attribution is not None:
                        referral_attribution_id = referral_attribution["id"]
                valid_referral = (
                    referral_account is not None
                    and referral_account["owner_user_id"] != user_id
                    and referral_attribution is not None
                )
                await self.tracking.record_source_touch(
                    conn,
                    user_id=user_id,
                    tracking_link_id=None,
                    raw_start_payload=start.raw,
                    touch_type=("referral" if valid_referral else ("organic" if is_new else "revisit")),
                )
            elif start.kind == StartKind.ORDER:
                # Internal Mini App → bot payment handoff. Do not count it as a new
                # acquisition touch; the original ad/referral attribution remains intact.
                pass
            else:
                await self.tracking.record_source_touch(
                    conn,
                    user_id=user_id,
                    tracking_link_id=None,
                    raw_start_payload=start.raw,
                    touch_type="organic" if is_new else "revisit",
                )

            display_language = user["preferred_language"]
            if display_language is None and resolved_link is not None:
                display_language = resolved_link["language_hint"]
            display_language = display_language or "am"

            if focus_product_id is not None:
                product_card = await self.products.get_sales_card(
                    conn,
                    product_id=focus_product_id,
                    language=display_language,
                )

            profile_completed = bool(profile and profile["onboarding_completed_at"])
            active_flow = (
                "sales"
                if profile_completed
                else ("entry" if not user["preferred_language"] else "onboarding")
            )
            step_key = (
                "resume"
                if profile_completed
                else ("language" if not user["preferred_language"] else "profile_role")
            )

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
                context={
                    "source_token": start.token,
                    "source_resolved": bool(resolved_link),
                },
            )

            event_payload = {
                "start_kind": start.kind.value,
                "start_token": start.token,
                "is_new_user": is_new,
            }
            if resolved_link is not None:
                event_payload.update(
                    {
                        "source": resolved_link["source"],
                        "platform": resolved_link["platform"],
                        "campaign": resolved_link["campaign"],
                        "creative": resolved_link["creative"],
                        "angle": resolved_link["angle"],
                    }
                )
            await self.events.append(
                conn,
                event_type="BOT_STARTED",
                user_id=user_id,
                product_id=focus_product_id,
                tracking_link_id=focus_tracking_link_id,
                payload=event_payload,
            )
            if is_new:
                await self.events.append(
                    conn,
                    event_type="USER_JOINED",
                    user_id=user_id,
                    product_id=focus_product_id,
                    tracking_link_id=focus_tracking_link_id,
                    payload=event_payload,
                )

            active_referral = await self.referrals.get_attribution_for_user(
                conn, referred_user_id=user_id
            )

            result = CustomerEntryContext(
                user_id=user_id,
                telegram_id=telegram_user.id,
                first_name=user["first_name"],
                username=user["username"],
                is_new_user=is_new,
                preferred_language=user["preferred_language"],
                profile_completed=profile_completed,
                customer_stage=user["customer_stage"],
                start_kind=start.kind,
                start_token=start.token,
                source_name=resolved_link["source"] if resolved_link else None,
                source_platform=resolved_link["platform"] if resolved_link else None,
                campaign=resolved_link["campaign"] if resolved_link else None,
                creative=resolved_link["creative"] if resolved_link else None,
                angle=resolved_link["angle"] if resolved_link else None,
                focus_product_id=focus_product_id,
                focus_product_title=product_card["title"] if product_card else None,
                focus_product_price_br=(
                    str(product_card["regular_price_br"]) if product_card else None
                ),
                referral_username=(
                    active_referral["referrer_username"] if active_referral else None
                ),
                referral_created=referral_created,
            )

        if result.is_new_user:
            await self._enqueue_new_user_ops(result)
        return result

    async def _enqueue_new_user_ops(self, entry: CustomerEntryContext) -> None:
        username = f"@{escape(entry.username)}" if entry.username else "No username"
        source = entry.source_name or ("Referral" if entry.start_kind == StartKind.REFERRAL else "Organic")
        creative = entry.creative or "—"
        product = entry.focus_product_title or "Not selected yet"
        referrer = f"@{escape(entry.referral_username)}" if entry.referral_username else "None"
        text = (
            "🆕 <b>NEW USER</b>\n\n"
            f"👤 <b>{escape(entry.first_name or 'Telegram user')}</b> · {username}\n"
            f"🆔 <code>{entry.telegram_id}</code>\n"
            f"📦 {escape(product)}\n"
            f"📣 {escape(source)} / {escape(creative)}\n"
            f"🤝 Referral: {referrer}"
        )
        await JobRepository(self.db).enqueue(
            EnqueueJob(
                job_type="telegram.ops.notify",
                queue="telegram",
                job_key=f"ops:new_user:{entry.user_id}",
                payload={"topic": "new_users", "text": text},
                max_attempts=8,
            )
        )
