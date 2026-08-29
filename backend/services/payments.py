from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from html import escape
from typing import Any
from uuid import UUID


from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.enums import PaymentRejectReason
from backend.domain.policies import POLICY_VERSION
from backend.domain.payments import (
    choose_checkout_price,
    new_order_public_id,
    new_payment_public_id,
    normalize_payment_method,
    normalize_reject_reason,
)
from backend.repositories.events import EventRepository
from backend.repositories.jobs import JobRepository
from backend.repositories.payments import PaymentRepository
from backend.repositories.sessions import ConversationSessionRepository
from backend.repositories.users import UserRepository
from workers.models import EnqueueJob


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    order_id: Any
    public_id: str
    product_id: Any
    product_slug: str
    product_title: str
    regular_price_br: Decimal
    total_due_br: Decimal
    pricing_type: str
    discount_br: Decimal
    commissionable: bool
    status: str
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class PaymentResume:
    order_public_id: str
    order_status: str
    product_title: str
    total_due_br: Decimal
    pricing_type: str
    payment_public_id: str | None
    payment_status: str | None
    payment_method: str | None
    rejection_reason: str | None
    policies_accepted: bool
    language: str


@dataclass(frozen=True, slots=True)
class ProofSubmission:
    payment_public_id: str
    order_public_id: str
    proof_id: Any
    flagged: bool
    duplicate_payment_public_id: str | None


@dataclass(frozen=True, slots=True)
class ReviewResult:
    changed: bool
    payment_public_id: str
    order_public_id: str
    product_title: str
    buyer_telegram_id: int
    buyer_name: str
    language: str
    status: str
    amount_br: Decimal


REJECTION_COPY = {
    PaymentRejectReason.WRONG_AMOUNT: {
        "am": "የተላከው የክፍያ መጠን ከትዕዛዙ ጋር አይዛመድም።",
        "en": "The paid amount doesn't match this order.",
    },
    PaymentRejectReason.WRONG_RECEIVER: {
        "am": "ክፍያው ወደተጠቀሰው የZemen Digital መቀበያ አልተላከም።",
        "en": "The payment was not sent to the listed Zemen Digital receiver.",
    },
    PaymentRejectReason.UNCLEAR_SCREENSHOT: {
        "am": "Screenshotው ግልጽ አይደለም። መጠንና transaction መረጃ የሚታይበትን ያስገቡ።",
        "en": "The screenshot isn't clear enough. Please resend one showing the amount and transaction details.",
    },
    PaymentRejectReason.OLD_TRANSACTION: {
        "am": "የተላከው transaction የዚህ ትዕዛዝ አይመስልም / የቆየ ነው።",
        "en": "The transaction appears old or unrelated to this order.",
    },
    PaymentRejectReason.DUPLICATE_RECEIPT: {
        "am": "ይህ receipt ከሌላ ክፍያ ጋር ተያይዞ ታይቷል።",
        "en": "This receipt appears to have been used with another payment.",
    },
    PaymentRejectReason.TRANSACTION_NOT_FOUND: {
        "am": "Transactionውን ማረጋገጥ አልቻልንም።",
        "en": "We couldn't verify this transaction.",
    },
    PaymentRejectReason.OTHER: {
        "am": "Paymentዎን በዚህ ማስረጃ ማረጋገጥ አልቻልንም።",
        "en": "We couldn't verify the payment from this proof.",
    },
}


class PaymentService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = PaymentRepository()
        self.users = UserRepository()
        self.sessions = ConversationSessionRepository()
        self.events = EventRepository()
        self.jobs = JobRepository(db)

    async def create_checkout(self, *, user_id: Any, product_slug: str) -> CheckoutResult:
        async with self.db.transaction() as conn:
            # Serializes double taps for the same user/product without Redis.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"checkout:{user_id}:{product_slug}",
            )
            product = await self.repo.get_product_for_checkout(
                conn, user_id=user_id, slug=product_slug
            )
            if product is None:
                raise LookupError("product not found")
            if product["is_owned"]:
                raise ValueError("product already owned")

            live = await self.repo.find_live_order_for_product(
                conn, user_id=user_id, product_id=product["id"]
            )
            offer_price = product["offer_price_br"]
            if live is not None:
                if offer_price is not None and Decimal(str(offer_price)) < Decimal(str(live["total_due_br"])):
                    await conn.execute(
                        "UPDATE orders SET status = 'cancelled', updated_at = now() WHERE id = $1",
                        live["id"],
                    )
                    live = None
                else:
                    item = await self.repo.order_product(
                        conn, order_id=live["id"], language="am"
                    )
                    return CheckoutResult(
                        order_id=live["id"],
                        public_id=live["public_id"],
                        product_id=product["id"],
                        product_slug=product["slug"],
                        product_title=item["title"] if item else product["slug"],
                        regular_price_br=Decimal(str(product["regular_price_br"])),
                        total_due_br=Decimal(str(live["total_due_br"])),
                        pricing_type=live["pricing_type"],
                        discount_br=Decimal(str(live["discount_total_br"])),
                        commissionable=live["pricing_type"] == "regular" and Decimal(str(live["discount_total_br"])) == 0,
                        status=live["status"],
                        expires_at=live["expires_at"],
                    )

            session = await self.sessions.get(conn, user_id=user_id)
            tracking_link_id = session["focus_tracking_link_id"] if session else None
            referral_attribution_id = session["referral_attribution_id"] if session else None
            offer_price = product["offer_price_br"]
            price = choose_checkout_price(
                regular_price_br=product["regular_price_br"],
                offer_price_br=offer_price,
            )
            referral_rate = (
                product["referral_commission_percent"]
                if referral_attribution_id is not None
                and product["referral_enabled"]
                and price.commissionable
                else Decimal("0")
            )
            expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.order_ttl_minutes)
            order = await self.repo.create_order(
                conn,
                public_id=new_order_public_id(),
                request_key=f"checkout:{user_id}:{product['id']}:{datetime.now(UTC).timestamp()}",
                user_id=user_id,
                product_id=product["id"],
                regular_price_br=price.regular_price_br,
                final_price_br=price.final_price_br,
                discount_br=price.discount_br,
                pricing_type=price.pricing_type.value,
                customer_offer_id=product["offer_id"],
                tracking_link_id=tracking_link_id,
                referral_attribution_id=referral_attribution_id,
                commissionable=price.commissionable,
                referral_rate_percent=referral_rate,
                expires_at=expires_at,
            )
            language = "am"
            user = await self.users.get_by_id(conn, user_id=user_id)
            if user and user["preferred_language"] == "en":
                language = "en"
            item = await self.repo.order_product(conn, order_id=order["id"], language=language)
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='payment', step_key='choose_payment_method',
                    focus_product_id=$2, active_order_id=$3, active_payment_id=NULL,
                    context=context || jsonb_build_object('checkout_public_id', $4::text),
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                user_id,
                product["id"],
                order["id"],
                order["public_id"],
            )
            await self.users.set_customer_stage(conn, user_id=user_id, stage="buy_clicked")
            await self.events.append(
                conn,
                event_type="ORDER_CREATED",
                user_id=user_id,
                product_id=product["id"],
                order_id=order["id"],
                tracking_link_id=tracking_link_id,
                payload={
                    "surface": "miniapp_or_bot",
                    "pricing_type": price.pricing_type.value,
                    "total_due_br": str(price.final_price_br),
                    "discount_br": str(price.discount_br),
                    "commissionable": price.commissionable,
                },
            )
            return CheckoutResult(
                order_id=order["id"],
                public_id=order["public_id"],
                product_id=product["id"],
                product_slug=product["slug"],
                product_title=item["title"] if item else product["slug"],
                regular_price_br=price.regular_price_br,
                total_due_br=price.final_price_br,
                pricing_type=price.pricing_type.value,
                discount_br=price.discount_br,
                commissionable=price.commissionable,
                status=order["status"],
                expires_at=expires_at,
            )

    async def resume_order_for_user(self, *, user_id: Any, order_public_id: str) -> PaymentResume:
        async with self.db.transaction() as conn:
            order = await self.repo.order_by_public_id_for_user(
                conn, public_id=order_public_id, user_id=user_id
            )
            if order is None:
                raise LookupError("order not found")
            user = await self.users.get_by_id(conn, user_id=user_id)
            language = "en" if user and user["preferred_language"] == "en" else "am"
            item = await self.repo.order_product(conn, order_id=order["id"], language=language)
            if item is None:
                raise LookupError("order product not found")
            if (
                order["status"] not in {"paid", "cancelled", "refunded"}
                and order["expires_at"]
                and order["expires_at"] <= datetime.now(UTC)
            ):
                await conn.execute(
                    "UPDATE orders SET status='expired', updated_at=now() WHERE id=$1",
                    order["id"],
                )
                order = await self.repo.order_by_public_id_for_user(
                    conn, public_id=order_public_id, user_id=user_id
                )
            payment = (
                await self.repo.latest_payment(conn, order_id=order["id"])
                if order["status"] in {"paid", "cancelled", "expired", "refunded"}
                else await self.repo.find_live_payment(conn, order_id=order["id"])
            )
            policies_accepted = bool(
                await conn.fetchval(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM legal_acceptances
                        WHERE user_id=$1 AND order_id=$2 AND policy_version=$3
                    )
                    """,
                    user_id,
                    order["id"],
                    POLICY_VERSION,
                )
            )
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='payment',
                    step_key=$3,
                    focus_product_id=$2,
                    active_order_id=$4,
                    active_payment_id=$5,
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                user_id,
                item["product_id"],
                (
                    "under_review" if payment and payment["status"] in {"pending_review", "flagged"}
                    else "needs_new_proof" if payment and payment["status"] == "rejected"
                    else "awaiting_proof" if payment
                    else "choose_payment_method"
                ),
                order["id"],
                payment["id"] if payment else None,
            )
            return PaymentResume(
                order_public_id=order["public_id"],
                order_status=order["status"],
                product_title=item["title"],
                total_due_br=Decimal(str(order["total_due_br"])),
                pricing_type=order["pricing_type"],
                payment_public_id=payment["public_id"] if payment else None,
                payment_status=payment["status"] if payment else None,
                payment_method=payment["payment_method"] if payment else None,
                rejection_reason=payment["rejection_reason_text"] if payment else None,
                policies_accepted=policies_accepted,
                language=language,
            )

    async def accept_purchase_policies(
        self,
        *,
        user_id: Any,
        order_public_id: str,
        language: str,
        surface: str = "telegram",
    ) -> PaymentResume:
        language = "en" if language == "en" else "am"
        if surface not in {"telegram", "miniapp"}:
            raise ValueError("invalid policy acceptance surface")
        async with self.db.transaction() as conn:
            order = await self.repo.order_by_public_id_for_user(
                conn, public_id=order_public_id, user_id=user_id, lock=True
            )
            if order is None:
                raise LookupError("order not found")
            if order["status"] in {"paid", "cancelled", "expired", "refunded"}:
                raise ValueError(f"order is {order['status']}")
            acceptance_id = await conn.fetchval(
                """
                INSERT INTO legal_acceptances(
                    user_id,order_id,policy_version,language,surface
                ) VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (user_id,order_id,policy_version) DO NOTHING
                RETURNING id
                """,
                user_id,
                order["id"],
                POLICY_VERSION,
                language,
                surface,
            )
            item = await self.repo.order_product(conn, order_id=order["id"], language=language)
            if acceptance_id is not None:
                await self.events.append(
                    conn,
                    event_type="PURCHASE_TERMS_ACCEPTED",
                    user_id=user_id,
                    product_id=item["product_id"] if item else None,
                    order_id=order["id"],
                    payload={
                        "policy_version": POLICY_VERSION,
                        "language": language,
                        "surface": surface,
                    },
                )
        return await self.resume_order_for_user(user_id=user_id, order_public_id=order_public_id)

    async def select_method(
        self,
        *,
        user_id: Any,
        order_public_id: str,
        method_value: str,
    ) -> PaymentResume:
        method = normalize_payment_method(method_value)
        async with self.db.transaction() as conn:
            order = await self.repo.order_by_public_id_for_user(
                conn, public_id=order_public_id, user_id=user_id, lock=True
            )
            if order is None:
                raise LookupError("order not found")
            if order["status"] in {"paid", "cancelled", "expired", "refunded"}:
                raise ValueError(f"order is {order['status']}")
            if order["expires_at"] and order["expires_at"] <= datetime.now(UTC):
                await conn.execute("UPDATE orders SET status='expired', updated_at=now() WHERE id=$1", order["id"])
                raise ValueError("order expired")
            accepted = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM legal_acceptances
                    WHERE user_id=$1 AND order_id=$2 AND policy_version=$3
                )
                """,
                user_id,
                order["id"],
                POLICY_VERSION,
            )
            if not accepted:
                raise ValueError("accept the Terms and Refund Policy before choosing payment")

            payment = await self.repo.find_live_payment(conn, order_id=order["id"], lock=True)
            if payment is None:
                payment = await self.repo.create_payment(
                    conn,
                    public_id=new_payment_public_id(),
                    order_id=order["id"],
                    user_id=user_id,
                    payment_method=method.value,
                    expected_amount_br=order["total_due_br"],
                    submission_key=f"payment:{order['public_id']}",
                )
            elif payment["status"] in {"awaiting_proof", "rejected"}:
                payment = await conn.fetchrow(
                    """
                    UPDATE payments
                    SET payment_method=$2,
                        status=CASE WHEN status='rejected' THEN 'awaiting_proof' ELSE status END,
                        rejection_reason_code=NULL, rejection_reason_text=NULL,
                        updated_at=now()
                    WHERE id=$1
                    RETURNING *
                    """,
                    payment["id"],
                    method.value,
                )
            elif payment["status"] in {"pending_review", "flagged"}:
                raise ValueError("payment proof is already under review")

            if order["status"] == "created":
                await conn.execute("UPDATE orders SET status='awaiting_payment', updated_at=now() WHERE id=$1", order["id"])
            await self.users.set_customer_stage(conn, user_id=user_id, stage="awaiting_payment")
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='payment', step_key='awaiting_proof',
                    active_order_id=$2, active_payment_id=$3,
                    context=context || jsonb_build_object('payment_method', $4::text),
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                user_id,
                order["id"],
                payment["id"],
                method.value,
            )
            item = await self.repo.order_product(conn, order_id=order["id"], language="am")
            await self.events.append(
                conn,
                event_type="PAYMENT_METHOD_SELECTED",
                user_id=user_id,
                product_id=item["product_id"] if item else None,
                order_id=order["id"],
                payload={"method": method.value, "payment_public_id": payment["public_id"]},
            )

        return await self.resume_order_for_user(user_id=user_id, order_public_id=order_public_id)

    async def submit_proof(
        self,
        *,
        user_id: Any,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
        telegram_media_type: str = "photo",
        caption: str | None = None,
    ) -> ProofSubmission:
        async with self.db.transaction() as conn:
            session = await self.sessions.get(conn, user_id=user_id)
            if session is None or session["active_payment_id"] is None:
                raise LookupError("no active payment")
            payment = await conn.fetchrow(
                "SELECT * FROM payments WHERE id=$1 AND user_id=$2 FOR UPDATE",
                session["active_payment_id"],
                user_id,
            )
            if payment is None:
                raise LookupError("active payment not found")
            if payment["status"] in {"approved", "cancelled"}:
                raise ValueError(f"payment is {payment['status']}")
            if payment["status"] in {"pending_review", "flagged"}:
                raise ValueError("payment is already under review")

            order = await conn.fetchrow("SELECT * FROM orders WHERE id=$1 FOR UPDATE", payment["order_id"])
            if order is None:
                raise LookupError("order not found")
            duplicate = await self.repo.duplicate_proof(
                conn,
                telegram_file_unique_id=telegram_file_unique_id,
                excluding_payment_id=payment["id"],
            )
            duplicate_signal = {}
            flagged = duplicate is not None
            if duplicate is not None:
                duplicate_signal = {
                    "duplicate_signal": True,
                    "other_payment_public_id": duplicate["payment_public_id"],
                    "other_payment_status": duplicate["payment_status"],
                }
            proof = await self.repo.insert_proof(
                conn,
                payment_id=payment["id"],
                user_id=user_id,
                telegram_file_id=telegram_file_id,
                telegram_file_unique_id=telegram_file_unique_id,
                telegram_media_type=telegram_media_type,
                caption=caption,
                duplicate_signal=duplicate_signal,
            )
            # A replacement screenshot invalidates any older review card immediately.
            await conn.execute(
                "UPDATE payment_review_messages SET status='superseded', updated_at=now() "
                "WHERE payment_id=$1 AND status IN ('open','flagged')",
                payment["id"],
            )
            if flagged:
                await conn.execute(
                    "UPDATE payment_proofs SET proof_status='flagged' WHERE id=$1",
                    proof["id"],
                )
            await conn.execute(
                "UPDATE payments SET status=$2, updated_at=now() WHERE id=$1",
                payment["id"],
                "flagged" if flagged else "pending_review",
            )
            await conn.execute(
                "UPDATE orders SET status='proof_submitted', updated_at=now() WHERE id=$1",
                order["id"],
            )
            await conn.execute(
                "UPDATE orders SET status='under_review', updated_at=now() WHERE id=$1",
                order["id"],
            )
            await self.users.set_customer_stage(conn, user_id=user_id, stage="proof_submitted")
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='payment', step_key='under_review',
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                user_id,
            )
            product = await self.repo.order_product(conn, order_id=order["id"], language="am")
            await self.events.append(
                conn,
                event_type="PROOF_UPLOADED",
                user_id=user_id,
                product_id=product["product_id"] if product else None,
                order_id=order["id"],
                payload={
                    "payment_public_id": payment["public_id"],
                    "proof_id": str(proof["id"]),
                    "duplicate_signal": flagged,
                },
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.ops.payment_review",
                    queue="telegram",
                    job_key=f"ops:payment_review:{proof['id']}",
                    payload={"payment_id": str(payment["id"]), "proof_id": str(proof["id"])},
                    max_attempts=8,
                ),
            )
            return ProofSubmission(
                payment_public_id=payment["public_id"],
                order_public_id=order["public_id"],
                proof_id=proof["id"],
                flagged=flagged,
                duplicate_payment_public_id=(duplicate["payment_public_id"] if duplicate else None),
            )

    async def is_admin(self, *, telegram_id: int) -> tuple[bool, Any | None]:
        if telegram_id in self.settings.admin_telegram_ids:
            async with self.db.acquire() as conn:
                row = await self.repo.admin_by_telegram_id(conn, telegram_id=telegram_id)
            return True, row["id"] if row else None
        async with self.db.acquire() as conn:
            row = await self.repo.admin_by_telegram_id(conn, telegram_id=telegram_id)
        return (row is not None), (row["id"] if row else None)

    async def review_proof_for_message(
        self,
        *,
        payment_public_id: str,
        chat_id: int,
        message_id: int,
    ) -> UUID:
        """Resolve the exact proof shown on a ZEMEN OPS review card.

        Telegram callbacks are payment-level, but approval must never silently act on a
        newer receipt than the one the admin is looking at. This mapping makes stale
        review cards fail closed.
        """
        async with self.db.acquire() as conn:
            row = await self.repo.review_message_context(
                conn, chat_id=chat_id, message_id=message_id
            )
        if row is None or row["payment_public_id"] != payment_public_id:
            raise LookupError("review card not found")
        if row["review_status"] not in {"open", "flagged"}:
            raise ValueError("this review card is no longer active")
        if row["latest_proof_id"] is None or row["proof_id"] != row["latest_proof_id"]:
            raise ValueError("a newer payment proof exists; review the newest card")
        return row["proof_id"]

    @staticmethod
    def _assert_expected_proof(payment: Any, expected_proof_id: UUID | None) -> None:
        if expected_proof_id is None:
            return
        if payment["latest_proof_id"] is None or payment["latest_proof_id"] != expected_proof_id:
            raise ValueError("a newer payment proof exists; review the newest card")

    async def approve(
        self,
        *,
        payment_public_id: str,
        admin_telegram_id: int,
        expected_proof_id: UUID | None = None,
    ) -> ReviewResult:
        allowed, admin_id = await self.is_admin(telegram_id=admin_telegram_id)
        if not allowed:
            raise PermissionError("admin access required")

        async with self.db.transaction() as conn:
            payment = await self.repo.payment_by_public_id(conn, public_id=payment_public_id, lock=True)
            if payment is None:
                raise LookupError("payment not found")
            self._assert_expected_proof(payment, expected_proof_id)
            order = await conn.fetchrow("SELECT * FROM orders WHERE id=$1 FOR UPDATE", payment["order_id"])
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            if order is None or context is None:
                raise LookupError("payment context missing")
            language = "en" if context["preferred_language"] == "en" else "am"
            if payment["status"] == "approved" and order["status"] == "paid":
                return self._review_result(context, changed=False, status="approved")
            if payment["status"] not in {"pending_review", "flagged"}:
                raise ValueError(f"payment cannot be approved from {payment['status']}")
            if payment["latest_proof_id"] is None:
                raise ValueError("payment has no proof")

            previous_entitlements = await conn.fetchval(
                "SELECT count(*) FROM entitlements WHERE user_id=$1 AND revoked_at IS NULL",
                payment["user_id"],
            )
            await conn.execute(
                """
                UPDATE payments
                SET status='approved', reviewed_by_admin_id=$2, reviewed_at=now(),
                    approved_at=now(), rejection_reason_code=NULL,
                    rejection_reason_text=NULL, updated_at=now()
                WHERE id=$1
                """,
                payment["id"],
                admin_id,
            )
            await conn.execute(
                "UPDATE orders SET status='paid', paid_at=now(), updated_at=now() WHERE id=$1",
                order["id"],
            )
            await conn.execute(
                "UPDATE payment_proofs SET proof_status='superseded' WHERE payment_id=$1 AND id<>$2 AND proof_status IN ('submitted','flagged')",
                payment["id"],
                payment["latest_proof_id"],
            )
            await conn.execute(
                "UPDATE payment_proofs SET proof_status='accepted' WHERE id=$1",
                payment["latest_proof_id"],
            )

            items = await conn.fetch(
                "SELECT * FROM order_items WHERE order_id=$1 ORDER BY created_at ASC",
                order["id"],
            )
            entitlement_ids: list[str] = []
            for item in items:
                file_id = await conn.fetchval(
                    """
                    SELECT id FROM product_files
                    WHERE product_id=$1 AND is_active=TRUE
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    item["product_id"],
                )
                entitlement = await conn.fetchrow(
                    """
                    INSERT INTO entitlements (
                        user_id, product_id, granted_by_order_id, product_file_id,
                        delivery_status
                    )
                    VALUES ($1,$2,$3,$4,'queued')
                    ON CONFLICT (user_id, product_id) DO UPDATE SET
                        product_file_id=COALESCE(EXCLUDED.product_file_id, entitlements.product_file_id),
                        delivery_status=CASE
                            WHEN entitlements.delivery_status='delivered' THEN 'delivered'
                            ELSE 'queued'
                        END,
                        metadata=entitlements.metadata || jsonb_build_object('latest_paid_order_id', $3::text)
                    RETURNING *
                    """,
                    payment["user_id"],
                    item["product_id"],
                    order["id"],
                    file_id,
                )
                entitlement_ids.append(str(entitlement["id"]))

            if order["customer_offer_id"] is not None:
                await conn.execute(
                    """
                    UPDATE customer_offers
                    SET status='redeemed', redeemed_at=now(), updated_at=now()
                    WHERE id=$1 AND status IN ('scheduled','available')
                    """,
                    order["customer_offer_id"],
                )

            # Locked rule: only regular/full-price orders can create commission.
            if (
                order["pricing_type"] == "regular"
                and Decimal(str(order["discount_total_br"])) == 0
                and order["referral_attribution_id"] is not None
            ):
                status_value = "available" if self.settings.commission_hold_days == 0 else "pending"
                for item in items:
                    if not item["commissionable"] or Decimal(str(item["referral_rate_percent_snapshot"])) <= 0:
                        continue
                    await conn.execute(
                        """
                        INSERT INTO commissions (
                            referral_attribution_id, order_id, order_item_id,
                            referrer_user_id, buyer_user_id, product_id,
                            gross_paid_br, rate_percent, amount_br, status,
                            available_at, rule_snapshot
                        )
                        SELECT
                            ra.id, $1, $2, ra.referrer_user_id, ra.referred_user_id, $3,
                            round(($4::numeric * $5::numeric)::numeric, 2),
                            $6,
                            round(($4::numeric * $5::numeric * $6::numeric / 100.0)::numeric, 2),
                            $7,
                            now() + make_interval(days => $8),
                            jsonb_build_object('full_price_only', true, 'pricing_type', 'regular')
                        FROM referral_attributions ra
                        WHERE ra.id=$9 AND ra.status='active'
                        ON CONFLICT (order_item_id) DO NOTHING
                        """,
                        order["id"],
                        item["id"],
                        item["product_id"],
                        item["unit_price_br"],
                        item["quantity"],
                        item["referral_rate_percent_snapshot"],
                        status_value,
                        self.settings.commission_hold_days,
                        order["referral_attribution_id"],
                    )

            stage = "repeat_customer" if int(previous_entitlements or 0) > 0 else "customer"
            await self.users.set_customer_stage(conn, user_id=payment["user_id"], stage=stage)
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='post_purchase', step_key='payment_approved',
                    active_payment_id=$2, active_order_id=$3,
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                payment["user_id"],
                payment["id"],
                order["id"],
            )
            await conn.execute(
                """
                UPDATE automation_runs
                SET status='stopped', completed_at=now(), updated_at=now(),
                    context=context || jsonb_build_object('stop_reason','purchase')
                WHERE user_id=$1 AND product_id=$2 AND status IN ('active','waiting')
                """,
                payment["user_id"],
                context["product_id"],
            )
            await conn.execute(
                "UPDATE payment_review_messages SET status='approved', updated_at=now() WHERE payment_id=$1 AND status IN ('open','flagged')",
                payment["id"],
            )
            await self.events.append(
                conn,
                event_type="PAYMENT_APPROVED",
                user_id=payment["user_id"],
                product_id=context["product_id"],
                order_id=order["id"],
                payload={"payment_public_id": payment["public_id"], "admin_telegram_id": admin_telegram_id},
            )
            await self.events.append(
                conn,
                event_type="PURCHASED",
                user_id=payment["user_id"],
                product_id=context["product_id"],
                order_id=order["id"],
                payload={
                    "amount_br": str(order["total_due_br"]),
                    "pricing_type": order["pricing_type"],
                    "commissionable": order["pricing_type"] == "regular" and Decimal(str(order["discount_total_br"])) == 0,
                },
            )
            await conn.execute(
                """
                INSERT INTO audit_logs (
                    actor_type, actor_admin_id, action, entity_type, entity_id,
                    after_data, metadata
                ) VALUES ('admin',$1,'payment.approve','payment',$2,$3::jsonb,$4::jsonb)
                """,
                admin_id,
                str(payment["id"]),
                {"status": "approved", "order_status": "paid"},
                {"admin_telegram_id": admin_telegram_id, "payment_public_id": payment["public_id"]},
            )

            approved_text = (
                f"✅ <b>Payment confirmed</b>\n\n📦 {escape(context['product_title'])}\n💰 {order['total_due_br']} Br\n\nYour product is being delivered here now. 🎉"
                if language == "en"
                else f"✅ <b>ክፍያዎ ተረጋግጧል</b>\n\n📦 {escape(context['product_title'])}\n💰 {order['total_due_br']} ብር\n\nምርትዎ አሁን እዚሁ ይደርስዎታል። 🎉"
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.user.notify",
                    queue="telegram",
                    job_key=f"user:payment_approved:{payment['id']}",
                    payload={
                        "telegram_id": int(context["telegram_id"]),
                        "text": approved_text,
                        "payment_action": "owned",
                        "order_public_id": order["public_id"],
                        "language": language,
                    },
                    max_attempts=8,
                ),
            )
            for entitlement_id in entitlement_ids:
                await self.jobs.enqueue_in_tx(
                    conn,
                    EnqueueJob(
                        job_type="telegram.delivery.product",
                        queue="delivery",
                        job_key=f"delivery:entitlement:{entitlement_id}",
                        payload={"entitlement_id": entitlement_id},
                        max_attempts=10,
                    ),
                )
            sale_text = (
                "✅ <b>NEW SALE</b>\n\n"
                f"👤 {escape(context['first_name'] or 'Customer')}\n"
                f"📦 {escape(context['product_title'])}\n"
                f"💰 <b>{order['total_due_br']} Br</b>\n"
                f"🏷 {escape(order['pricing_type'])}\n"
                f"🤝 Commission: {'Eligible' if order['pricing_type']=='regular' and order['referral_attribution_id'] else '0 Br / not eligible'}\n"
                f"🧾 <code>{order['public_id']}</code>"
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.ops.notify",
                    queue="telegram",
                    job_key=f"ops:sale:{order['id']}",
                    payload={"topic": "sales", "text": sale_text},
                    max_attempts=8,
                ),
            )
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            if context is None:
                raise RuntimeError("review context disappeared")
            return self._review_result(context, changed=True, status="approved")

    async def reject(
        self,
        *,
        payment_public_id: str,
        reason_value: str,
        admin_telegram_id: int,
        reason_text: str | None = None,
        expected_proof_id: UUID | None = None,
    ) -> ReviewResult:
        allowed, admin_id = await self.is_admin(telegram_id=admin_telegram_id)
        if not allowed:
            raise PermissionError("admin access required")
        reason = normalize_reject_reason(reason_value)
        async with self.db.transaction() as conn:
            payment = await self.repo.payment_by_public_id(conn, public_id=payment_public_id, lock=True)
            if payment is None:
                raise LookupError("payment not found")
            self._assert_expected_proof(payment, expected_proof_id)
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            if context is None:
                raise LookupError("payment context missing")
            if payment["status"] == "approved":
                raise ValueError("approved payment cannot be rejected")
            if payment["status"] == "rejected" and payment["rejection_reason_code"] == reason.value:
                return self._review_result(context, changed=False, status="rejected")
            if payment["status"] not in {"pending_review", "flagged"}:
                raise ValueError(f"payment cannot be rejected from {payment['status']}")

            language = "en" if context["preferred_language"] == "en" else "am"
            final_reason = (reason_text or REJECTION_COPY[reason][language]).strip()
            await conn.execute(
                """
                UPDATE payments
                SET status='rejected', rejection_reason_code=$2,
                    rejection_reason_text=$3, reviewed_by_admin_id=$4,
                    reviewed_at=now(), updated_at=now()
                WHERE id=$1
                """,
                payment["id"],
                reason.value,
                final_reason,
                admin_id,
            )
            if payment["latest_proof_id"]:
                await conn.execute(
                    "UPDATE payment_proofs SET proof_status='rejected' WHERE id=$1",
                    payment["latest_proof_id"],
                )
            await conn.execute(
                "UPDATE orders SET status='needs_new_proof', updated_at=now() WHERE id=$1",
                payment["order_id"],
            )
            await self.users.set_customer_stage(conn, user_id=payment["user_id"], stage="payment_rejected")
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='payment', step_key='needs_new_proof',
                    active_payment_id=$2, active_order_id=$3,
                    last_interaction_at=now(), updated_at=now()
                WHERE user_id=$1
                """,
                payment["user_id"],
                payment["id"],
                payment["order_id"],
            )
            await conn.execute(
                "UPDATE payment_review_messages SET status='rejected', updated_at=now() WHERE payment_id=$1 AND status IN ('open','flagged')",
                payment["id"],
            )
            await self.events.append(
                conn,
                event_type="PROOF_REJECTED",
                user_id=payment["user_id"],
                product_id=context["product_id"],
                order_id=payment["order_id"],
                payload={"reason": reason.value, "payment_public_id": payment["public_id"]},
            )
            await conn.execute(
                """
                INSERT INTO audit_logs (
                    actor_type, actor_admin_id, action, entity_type, entity_id,
                    after_data, metadata
                ) VALUES ('admin',$1,'payment.reject','payment',$2,$3::jsonb,$4::jsonb)
                """,
                admin_id,
                str(payment["id"]),
                {"status": "rejected", "reason": reason.value, "reason_text": final_reason},
                {"admin_telegram_id": admin_telegram_id, "payment_public_id": payment["public_id"]},
            )
            user_text = (
                f"❌ <b>Payment needs another proof</b>\n\n📦 {escape(context['product_title'])}\n\n<b>Reason:</b> {escape(final_reason)}\n\n📸 Please send a new screenshot here. Your order is still saved."
                if language == "en"
                else f"❌ <b>ክፍያዎ እንደገና ማስረጃ ይፈልጋል</b>\n\n📦 {escape(context['product_title'])}\n\n<b>ምክንያት:</b> {escape(final_reason)}\n\n📸 እባክዎ አዲስ screenshot እዚሁ ይላኩ። ትዕዛዝዎ አልጠፋም።"
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.user.notify",
                    queue="telegram",
                    job_key=f"user:payment_rejected:{payment['id']}:{payment['latest_proof_id']}",
                    payload={
                        "telegram_id": int(context["telegram_id"]),
                        "text": user_text,
                        "payment_action": "rejected",
                        "order_public_id": context["order_public_id"],
                        "language": language,
                    },
                    max_attempts=8,
                ),
            )
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            return self._review_result(context, changed=True, status="rejected")

    async def flag(
        self,
        *,
        payment_public_id: str,
        admin_telegram_id: int,
        expected_proof_id: UUID | None = None,
    ) -> ReviewResult:
        allowed, admin_id = await self.is_admin(telegram_id=admin_telegram_id)
        if not allowed:
            raise PermissionError("admin access required")
        async with self.db.transaction() as conn:
            payment = await self.repo.payment_by_public_id(conn, public_id=payment_public_id, lock=True)
            if payment is None:
                raise LookupError("payment not found")
            self._assert_expected_proof(payment, expected_proof_id)
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            if context is None:
                raise LookupError("payment context missing")
            if payment["status"] == "flagged":
                return self._review_result(context, changed=False, status="flagged")
            if payment["status"] != "pending_review":
                raise ValueError(f"payment cannot be flagged from {payment['status']}")
            await conn.execute(
                "UPDATE payments SET status='flagged', reviewed_by_admin_id=$2, reviewed_at=now(), updated_at=now() WHERE id=$1",
                payment["id"],
                admin_id,
            )
            if payment["latest_proof_id"]:
                await conn.execute("UPDATE payment_proofs SET proof_status='flagged' WHERE id=$1", payment["latest_proof_id"])
            await conn.execute("UPDATE payment_review_messages SET status='flagged', updated_at=now() WHERE payment_id=$1 AND status='open'", payment["id"])
            await self.events.append(
                conn,
                event_type="PAYMENT_FLAGGED",
                user_id=payment["user_id"],
                product_id=context["product_id"],
                order_id=payment["order_id"],
                payload={"payment_public_id": payment["public_id"], "admin_telegram_id": admin_telegram_id},
            )
            context = await self.repo.review_context(conn, payment_id=payment["id"])
            return self._review_result(context, changed=True, status="flagged")

    @staticmethod
    def _review_result(context: Any, *, changed: bool, status: str) -> ReviewResult:
        return ReviewResult(
            changed=changed,
            payment_public_id=context["payment_public_id"],
            order_public_id=context["order_public_id"],
            product_title=context["product_title"],
            buyer_telegram_id=int(context["telegram_id"]),
            buyer_name=context["first_name"] or "Customer",
            language="en" if context["preferred_language"] == "en" else "am",
            status=status,
            amount_br=Decimal(str(context["expected_amount_br"])),
        )
