from __future__ import annotations

from typing import Any

import asyncpg


class PaymentRepository:
    async def get_product_for_checkout(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        slug: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                p.*,
                offer.id AS offer_id,
                offer.offer_price_br,
                offer.expires_at AS offer_expires_at,
                (ent.user_id IS NOT NULL) AS is_owned
            FROM products p
            LEFT JOIN LATERAL (
                SELECT co.id, co.offer_price_br, co.expires_at
                FROM customer_offers co
                WHERE co.user_id = $1
                  AND co.product_id = p.id
                  AND co.status = 'available'
                  AND (co.starts_at IS NULL OR co.starts_at <= now())
                  AND (co.expires_at IS NULL OR co.expires_at > now())
                ORDER BY co.created_at DESC
                LIMIT 1
            ) offer ON TRUE
            LEFT JOIN entitlements ent
                ON ent.user_id = $1
               AND ent.product_id = p.id
               AND ent.revoked_at IS NULL
            WHERE p.slug = $2
              AND p.status = 'active'
            """,
            user_id,
            slug,
        )

    async def find_live_order_for_product(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT o.*
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            WHERE o.user_id = $1
              AND oi.product_id = $2
              AND o.status IN (
                  'created', 'awaiting_payment', 'proof_submitted',
                  'under_review', 'needs_new_proof'
              )
              AND (o.expires_at IS NULL OR o.expires_at > now())
            ORDER BY o.created_at DESC
            LIMIT 1
            FOR UPDATE OF o
            """,
            user_id,
            product_id,
        )

    async def create_order(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        request_key: str,
        user_id: Any,
        product_id: Any,
        regular_price_br: Any,
        final_price_br: Any,
        discount_br: Any,
        pricing_type: str,
        customer_offer_id: Any | None,
        tracking_link_id: Any | None,
        referral_attribution_id: Any | None,
        commissionable: bool,
        referral_rate_percent: Any,
        expires_at: Any,
    ) -> asyncpg.Record:
        order = await conn.fetchrow(
            """
            INSERT INTO orders (
                public_id, request_key, user_id, status, currency,
                subtotal_br, discount_total_br, total_due_br, pricing_type,
                customer_offer_id, source_tracking_link_id,
                referral_attribution_id, expires_at
            )
            VALUES ($1, $2, $3, 'created', 'ETB', $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            public_id,
            request_key,
            user_id,
            regular_price_br,
            discount_br,
            final_price_br,
            pricing_type,
            customer_offer_id,
            tracking_link_id,
            referral_attribution_id,
            expires_at,
        )
        await conn.execute(
            """
            INSERT INTO order_items (
                order_id, product_id, quantity,
                regular_unit_price_br, unit_price_br, discount_per_unit_br,
                commissionable, referral_rate_percent_snapshot
            )
            VALUES ($1, $2, 1, $3, $4, $5, $6, $7)
            """,
            order["id"],
            product_id,
            regular_price_br,
            final_price_br,
            discount_br,
            commissionable,
            referral_rate_percent,
        )
        return order

    async def order_by_public_id_for_user(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        user_id: Any,
        lock: bool = False,
    ) -> asyncpg.Record | None:
        suffix = " FOR UPDATE" if lock else ""
        return await conn.fetchrow(
            f"SELECT * FROM orders WHERE public_id=$1 AND user_id=$2{suffix}",
            public_id,
            user_id,
        )

    async def order_product(
        self,
        conn: asyncpg.Connection,
        *,
        order_id: Any,
        language: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                p.id AS product_id,
                p.slug,
                p.regular_price_br,
                p.referral_enabled,
                p.referral_commission_percent,
                COALESCE(pt.title, fallback.title, p.slug) AS title,
                oi.id AS order_item_id,
                oi.unit_price_br,
                oi.discount_per_unit_br,
                oi.commissionable,
                oi.referral_rate_percent_snapshot
            FROM order_items oi
            JOIN products p ON p.id = oi.product_id
            LEFT JOIN product_translations pt
                ON pt.product_id = p.id AND pt.language = $2
            LEFT JOIN product_translations fallback
                ON fallback.product_id = p.id AND fallback.language = p.default_language
            WHERE oi.order_id = $1
            ORDER BY oi.created_at ASC
            LIMIT 1
            """,
            order_id,
            language,
        )

    async def find_live_payment(
        self,
        conn: asyncpg.Connection,
        *,
        order_id: Any,
        lock: bool = False,
    ) -> asyncpg.Record | None:
        suffix = " FOR UPDATE" if lock else ""
        return await conn.fetchrow(
            f"""
            SELECT * FROM payments
            WHERE order_id=$1
              AND status IN ('awaiting_proof','pending_review','flagged','rejected')
            ORDER BY created_at DESC
            LIMIT 1{suffix}
            """,
            order_id,
        )

    async def latest_payment(
        self,
        conn: asyncpg.Connection,
        *,
        order_id: Any,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT * FROM payments
            WHERE order_id=$1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            order_id,
        )

    async def create_payment(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        order_id: Any,
        user_id: Any,
        payment_method: str,
        expected_amount_br: Any,
        submission_key: str,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO payments (
                public_id, order_id, user_id, payment_method,
                expected_amount_br, status, submission_key
            )
            VALUES ($1, $2, $3, $4, $5, 'awaiting_proof', $6)
            RETURNING *
            """,
            public_id,
            order_id,
            user_id,
            payment_method,
            expected_amount_br,
            submission_key,
        )

    async def payment_by_public_id_for_user(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        user_id: Any,
        lock: bool = False,
    ) -> asyncpg.Record | None:
        suffix = " FOR UPDATE" if lock else ""
        return await conn.fetchrow(
            f"SELECT * FROM payments WHERE public_id=$1 AND user_id=$2{suffix}",
            public_id,
            user_id,
        )

    async def payment_by_public_id(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        lock: bool = False,
    ) -> asyncpg.Record | None:
        suffix = " FOR UPDATE" if lock else ""
        return await conn.fetchrow(
            f"SELECT * FROM payments WHERE public_id=$1{suffix}",
            public_id,
        )

    async def duplicate_proof(
        self,
        conn: asyncpg.Connection,
        *,
        telegram_file_unique_id: str | None,
        excluding_payment_id: Any,
    ) -> asyncpg.Record | None:
        if not telegram_file_unique_id:
            return None
        return await conn.fetchrow(
            """
            SELECT pp.*, p.public_id AS payment_public_id, p.status AS payment_status
            FROM payment_proofs pp
            JOIN payments p ON p.id = pp.payment_id
            WHERE pp.telegram_file_unique_id=$1
              AND pp.payment_id <> $2
            ORDER BY pp.created_at DESC
            LIMIT 1
            """,
            telegram_file_unique_id,
            excluding_payment_id,
        )

    async def insert_proof(
        self,
        conn: asyncpg.Connection,
        *,
        payment_id: Any,
        user_id: Any,
        telegram_file_id: str,
        telegram_file_unique_id: str | None,
        telegram_media_type: str,
        caption: str | None,
        duplicate_signal: dict[str, object] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO payment_proofs (
                payment_id, telegram_file_id, telegram_file_unique_id, telegram_media_type,
                submitted_by_user_id, proof_status, caption, verifier_data
            )
            VALUES ($1, $2, $3, $4, $5, 'submitted', $6, $7::jsonb)
            RETURNING *
            """,
            payment_id,
            telegram_file_id,
            telegram_file_unique_id,
            telegram_media_type,
            user_id,
            caption,
            duplicate_signal or {},
        )

    async def review_context(
        self,
        conn: asyncpg.Connection,
        *,
        payment_id: Any,
        proof_id: Any | None = None,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                p.id AS payment_id,
                p.public_id AS payment_public_id,
                p.status AS payment_status,
                p.payment_method,
                p.expected_amount_br,
                p.latest_proof_id,
                p.rejection_reason_code,
                p.rejection_reason_text,
                o.id AS order_id,
                o.public_id AS order_public_id,
                o.status AS order_status,
                o.pricing_type,
                o.discount_total_br,
                o.total_due_br,
                o.referral_attribution_id,
                u.id AS user_id,
                u.telegram_id,
                u.first_name,
                u.last_name,
                u.username,
                u.preferred_language,
                pr.id AS product_id,
                pr.slug AS product_slug,
                COALESCE(pt.title, fallback.title, pr.slug) AS product_title,
                pp.id AS proof_id,
                pp.telegram_file_id,
                pp.telegram_file_unique_id,
                pp.telegram_media_type,
                pp.proof_status,
                pp.verifier_data,
                ra.referrer_user_id,
                ref.username AS referrer_username,
                oi.commissionable,
                oi.referral_rate_percent_snapshot
            FROM payments p
            JOIN orders o ON o.id = p.order_id
            JOIN users u ON u.id = p.user_id
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products pr ON pr.id = oi.product_id
            LEFT JOIN product_translations pt
                ON pt.product_id = pr.id AND pt.language = COALESCE(u.preferred_language, 'am')
            LEFT JOIN product_translations fallback
                ON fallback.product_id = pr.id AND fallback.language = pr.default_language
            LEFT JOIN payment_proofs pp
                ON pp.id = COALESCE($2::uuid, p.latest_proof_id)
            LEFT JOIN referral_attributions ra ON ra.id = o.referral_attribution_id
            LEFT JOIN users ref ON ref.id = ra.referrer_user_id
            WHERE p.id = $1
            ORDER BY oi.created_at ASC
            LIMIT 1
            """,
            payment_id,
            proof_id,
        )

    async def record_review_message(
        self,
        conn: asyncpg.Connection,
        *,
        payment_id: Any,
        proof_id: Any,
        chat_id: int,
        thread_id: int | None,
        message_id: int,
    ) -> asyncpg.Record:
        await conn.execute(
            """
            UPDATE payment_review_messages
            SET status='superseded', updated_at=now()
            WHERE payment_id=$1 AND status='open'
            """,
            payment_id,
        )
        return await conn.fetchrow(
            """
            INSERT INTO payment_review_messages (
                payment_id, proof_id, ops_chat_id, ops_thread_id, ops_message_id, status
            )
            VALUES ($1,$2,$3,$4,$5,'open')
            ON CONFLICT (ops_chat_id, ops_message_id) DO UPDATE SET
                payment_id=EXCLUDED.payment_id,
                proof_id=EXCLUDED.proof_id,
                ops_thread_id=EXCLUDED.ops_thread_id,
                status='open',
                updated_at=now()
            RETURNING *
            """,
            payment_id,
            proof_id,
            chat_id,
            thread_id,
            message_id,
        )

    async def review_message_context(
        self,
        conn: asyncpg.Connection,
        *,
        chat_id: int,
        message_id: int,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                prm.payment_id, prm.proof_id, prm.status AS review_status,
                p.public_id AS payment_public_id, p.latest_proof_id, p.status AS payment_status
            FROM payment_review_messages prm
            JOIN payments p ON p.id = prm.payment_id
            WHERE prm.ops_chat_id=$1 AND prm.ops_message_id=$2
            """,
            chat_id,
            message_id,
        )

    async def admin_by_telegram_id(
        self,
        conn: asyncpg.Connection,
        *,
        telegram_id: int,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            telegram_id,
        )
