from __future__ import annotations

from typing import Any

import asyncpg


class ProductRepository:
    async def get_active_by_id(
        self, conn: asyncpg.Connection, product_id: Any
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM products WHERE id = $1 AND status = 'active'",
            product_id,
        )

    async def get_active_by_slug(
        self, conn: asyncpg.Connection, slug: str
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT * FROM products WHERE slug = $1 AND status = 'active'",
            slug,
        )

    async def get_translation(
        self,
        conn: asyncpg.Connection,
        *,
        product_id: Any,
        language: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT *
            FROM product_translations
            WHERE product_id = $1 AND language = $2
            """,
            product_id,
            language,
        )

    async def get_sales_card(
        self,
        conn: asyncpg.Connection,
        *,
        product_id: Any,
        language: str,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT
                p.id, p.slug, p.regular_price_br, p.recovery_price_br,
                p.discounts_enabled, p.referral_enabled,
                p.referral_commission_percent, p.default_language,
                COALESCE(pt.title, fallback.title, p.slug) AS title,
                COALESCE(pt.subtitle, fallback.subtitle) AS subtitle,
                COALESCE(pt.short_description, fallback.short_description) AS short_description
            FROM products p
            LEFT JOIN product_translations pt
                ON pt.product_id = p.id AND pt.language = $2
            LEFT JOIN product_translations fallback
                ON fallback.product_id = p.id AND fallback.language = p.default_language
            WHERE p.id = $1 AND p.status = 'active'
            """,
            product_id,
            language,
        )
    
    
    async def list_active_sales_cards(
        self,
        conn: asyncpg.Connection,
        *,
        language: str,
    ) -> list[asyncpg.Record]:
        return await conn.fetch(
            """
            SELECT
                p.id,
                p.slug,
                p.regular_price_br,
                COALESCE(pt.title, fallback.title, p.slug) AS title,
                COALESCE(pt.short_description, fallback.short_description) AS short_description
            FROM products p
            LEFT JOIN product_translations pt
                ON pt.product_id = p.id
            AND pt.language = $1
            LEFT JOIN product_translations fallback
                ON fallback.product_id = p.id
            AND fallback.language = p.default_language
            WHERE p.status = 'active'
            ORDER BY p.created_at DESC
            """,
            language,
        )
