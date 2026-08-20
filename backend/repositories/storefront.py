from __future__ import annotations

from typing import Any

import asyncpg


class StorefrontRepository:
    async def list_products(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        language: str,
        limit: int = 50,
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT
                    p.id,
                    p.slug,
                    p.featured,
                    p.regular_price_br,
                    p.recovery_price_br,
                    p.discounts_enabled,
                    p.referral_enabled,
                    p.referral_commission_percent,
                    COALESCE(pt.title, fallback.title, p.slug) AS title,
                    COALESCE(pt.subtitle, fallback.subtitle) AS subtitle,
                    COALESCE(pt.short_description, fallback.short_description, '') AS short_description,
                    media.id AS cover_media_id,
                    media.storage_type AS cover_storage_type,
                    media.value AS cover_value,
                    offer.id AS offer_id,
                    offer.offer_price_br,
                    offer.expires_at AS offer_expires_at,
                    (ent.user_id IS NOT NULL) AS is_owned
                FROM products p
                LEFT JOIN product_translations pt
                    ON pt.product_id = p.id AND pt.language = $2
                LEFT JOIN product_translations fallback
                    ON fallback.product_id = p.id AND fallback.language = p.default_language
                LEFT JOIN LATERAL (
                    SELECT pm.id, pm.storage_type, pm.value
                    FROM product_media pm
                    WHERE pm.product_id = p.id
                      AND pm.is_active = TRUE
                      AND pm.media_type IN ('cover', 'thumbnail')
                      AND (pm.language = $2 OR pm.language IS NULL)
                    ORDER BY
                        CASE WHEN pm.language = $2 THEN 0 ELSE 1 END,
                        CASE WHEN pm.media_type = 'cover' THEN 0 ELSE 1 END,
                        pm.sort_order ASC,
                        pm.created_at ASC
                    LIMIT 1
                ) media ON TRUE
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
                WHERE p.status = 'active'
                ORDER BY p.featured DESC, p.sort_order ASC, p.created_at DESC
                LIMIT $3
                """,
                user_id,
                language,
                limit,
            )
        )

    async def get_product_detail(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        slug: str,
        language: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                p.id,
                p.slug,
                p.product_type,
                p.category,
                p.featured,
                p.regular_price_br,
                p.recovery_price_br,
                p.discounts_enabled,
                p.referral_enabled,
                p.referral_commission_percent,
                COALESCE(pt.title, fallback.title, p.slug) AS title,
                COALESCE(pt.subtitle, fallback.subtitle) AS subtitle,
                COALESCE(pt.short_description, fallback.short_description, '') AS short_description,
                COALESCE(pt.description, fallback.description, '') AS description,
                COALESCE(pt.benefits, fallback.benefits, '[]'::jsonb) AS benefits,
                COALESCE(pt.faq, fallback.faq, '[]'::jsonb) AS faq,
                offer.id AS offer_id,
                offer.offer_price_br,
                offer.expires_at AS offer_expires_at,
                (ent.user_id IS NOT NULL) AS is_owned,
                COALESCE(review_stats.review_count, 0) AS review_count,
                review_stats.avg_rating
            FROM products p
            LEFT JOIN product_translations pt
                ON pt.product_id = p.id AND pt.language = $3
            LEFT JOIN product_translations fallback
                ON fallback.product_id = p.id AND fallback.language = p.default_language
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
            LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS review_count, ROUND(AVG(r.rating)::numeric, 1) AS avg_rating
                FROM reviews r
                WHERE r.product_id = p.id
                  AND r.status = 'approved'
                  AND r.rating IS NOT NULL
            ) review_stats ON TRUE
            WHERE p.slug = $2 AND p.status = 'active'
            """,
            user_id,
            slug,
            language,
        )

    async def list_product_media(
        self,
        conn: asyncpg.Connection,
        *,
        product_id: Any,
        language: str,
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT id, media_type, storage_type, value, alt_text, sort_order
                FROM product_media
                WHERE product_id = $1
                  AND is_active = TRUE
                  AND media_type IN ('cover', 'gallery', 'preview', 'thumbnail', 'video')
                  AND (language = $2 OR language IS NULL)
                ORDER BY
                    CASE WHEN language = $2 THEN 0 ELSE 1 END,
                    CASE media_type
                        WHEN 'cover' THEN 0
                        WHEN 'thumbnail' THEN 1
                        WHEN 'preview' THEN 2
                        WHEN 'gallery' THEN 3
                        WHEN 'video' THEN 4
                        ELSE 5
                    END,
                    sort_order ASC,
                    created_at ASC
                """,
                product_id,
                language,
            )
        )

    async def list_featured_reviews(
        self,
        conn: asyncpg.Connection,
        *,
        product_id: Any,
        language: str,
        limit: int = 4,
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT r.rating, r.review_text, r.language, u.first_name
                FROM reviews r
                JOIN users u ON u.id = r.user_id
                WHERE r.product_id = $1
                  AND r.status = 'approved'
                  AND r.review_text IS NOT NULL
                  AND (r.language = $2 OR r.language IS NULL)
                ORDER BY r.featured DESC, r.created_at DESC
                LIMIT $3
                """,
                product_id,
                language,
                limit,
            )
        )

    async def list_library(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        language: str,
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT
                    e.id AS entitlement_id,
                    e.product_id,
                    e.delivery_status,
                    e.granted_at,
                    e.delivered_at,
                    p.slug,
                    COALESCE(pt.title, fallback.title, p.slug) AS title,
                    COALESCE(pt.short_description, fallback.short_description, '') AS short_description,
                    pf.version,
                    media.id AS cover_media_id,
                    media.storage_type AS cover_storage_type,
                    media.value AS cover_value,
                    r.id AS review_id,
                    r.rating AS review_rating,
                    r.review_text,
                    r.status AS review_status
                FROM entitlements e
                JOIN products p ON p.id = e.product_id
                LEFT JOIN product_translations pt
                    ON pt.product_id = p.id AND pt.language = $2
                LEFT JOIN product_translations fallback
                    ON fallback.product_id = p.id AND fallback.language = p.default_language
                LEFT JOIN product_files pf ON pf.id = e.product_file_id
                LEFT JOIN LATERAL (
                    SELECT pm.id, pm.storage_type, pm.value
                    FROM product_media pm
                    WHERE pm.product_id = p.id
                      AND pm.is_active = TRUE
                      AND pm.media_type IN ('cover', 'thumbnail')
                      AND (pm.language = $2 OR pm.language IS NULL)
                    ORDER BY
                        CASE WHEN pm.language = $2 THEN 0 ELSE 1 END,
                        CASE WHEN pm.media_type = 'cover' THEN 0 ELSE 1 END,
                        pm.sort_order ASC
                    LIMIT 1
                ) media ON TRUE
                LEFT JOIN reviews r
                    ON r.user_id=e.user_id AND r.product_id=e.product_id AND r.source='customer'
                WHERE e.user_id = $1
                  AND e.revoked_at IS NULL
                ORDER BY e.granted_at DESC
                """,
                user_id,
                language,
            )
        )


    async def submit_review(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        product_id: Any,
        order_id: Any,
        rating: int,
        review_text: str,
        language: str,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO reviews(user_id,product_id,order_id,rating,review_text,language,status,featured,source)
            VALUES($1,$2,$3,$4,$5,$6,'pending',FALSE,'customer')
            ON CONFLICT(user_id,product_id) WHERE source='customer'
            DO UPDATE SET order_id=excluded.order_id,rating=excluded.rating,review_text=excluded.review_text,
                          language=excluded.language,status='pending',featured=FALSE,moderated_by_admin_id=NULL,
                          moderated_at=NULL,updated_at=now()
            RETURNING *
            """,
            user_id, product_id, order_id, rating, review_text, language,
        )

    async def review_purchase_context(
        self, conn: asyncpg.Connection, *, user_id: Any, slug: str
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT p.id AS product_id,o.id AS order_id
            FROM products p
            JOIN order_items oi ON oi.product_id=p.id
            JOIN orders o ON o.id=oi.order_id
            WHERE p.slug=$2 AND o.user_id=$1 AND o.status='paid'
            ORDER BY o.paid_at DESC NULLS LAST,o.created_at DESC
            LIMIT 1
            """,
            user_id,slug,
        )

    async def get_referral_account(
        self, conn: asyncpg.Connection, *, user_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM referral_accounts WHERE owner_user_id = $1",
            user_id,
        )

    async def create_referral_account(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
        code: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            INSERT INTO referral_accounts (owner_user_id, code)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            RETURNING *
            """,
            user_id,
            code,
        )

    async def referral_stats(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            SELECT
                (SELECT COUNT(*)::int
                   FROM referral_attributions ra
                  WHERE ra.referrer_user_id = $1 AND ra.status = 'active') AS joins,
                (SELECT COUNT(DISTINCT c.buyer_user_id)::int
                   FROM commissions c
                  WHERE c.referrer_user_id = $1 AND c.status <> 'void') AS full_price_buyers,
                (SELECT COALESCE(SUM(c.amount_br), 0)::numeric(12,2)
                   FROM commissions c
                  WHERE c.referrer_user_id = $1 AND c.status = 'pending') AS pending_br,
                (SELECT COALESCE(SUM(c.amount_br), 0)::numeric(12,2)
                   FROM commissions c
                  WHERE c.referrer_user_id = $1 AND c.status = 'available') AS available_br,
                (SELECT COALESCE(SUM(c.amount_br), 0)::numeric(12,2)
                   FROM commissions c
                  WHERE c.referrer_user_id = $1 AND c.status = 'paid') AS paid_br
            """,
            user_id,
        )

    async def referral_program_rate(self, conn: asyncpg.Connection) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            SELECT
                COALESCE(MAX(referral_commission_percent), 0)::numeric(5,2) AS max_rate,
                BOOL_AND(commission_only_full_price) AS full_price_only
            FROM products
            WHERE status = 'active' AND referral_enabled = TRUE
            """
        )

    async def current_focus_product(
        self,
        conn: asyncpg.Connection,
        *,
        user_id: Any,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT p.id, p.slug
            FROM conversation_sessions cs
            JOIN products p ON p.id = cs.focus_product_id
            WHERE cs.user_id = $1 AND p.status = 'active'
            """,
            user_id,
        )
