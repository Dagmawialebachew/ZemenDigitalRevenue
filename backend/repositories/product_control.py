from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


class ProductControlRepository:
    async def list_products(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT p.id,p.slug,p.status,p.product_type,p.category,p.default_language,
                   p.regular_price_br,p.recovery_price_br,p.discounts_enabled,p.referral_enabled,
                   p.referral_commission_percent,p.commission_only_full_price,p.featured,p.sort_order,
                   p.revision,p.updated_at,
                   COALESCE(am.title,en.title,p.slug) AS title,
                   COALESCE((SELECT count(*) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id AND o.status='paid'),0) AS sales_count,
                   COALESCE((SELECT sum(oi.unit_price_br*oi.quantity) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id AND o.status='paid'),0) AS revenue_br,
                   (SELECT pm.id FROM product_media pm WHERE pm.product_id=p.id AND pm.media_type IN ('cover','thumbnail') AND pm.is_active=TRUE ORDER BY CASE pm.media_type WHEN 'cover' THEN 0 ELSE 1 END, pm.sort_order LIMIT 1) AS cover_media_id,
                   (SELECT storage_type FROM product_media pm WHERE pm.product_id=p.id AND pm.media_type IN ('cover','thumbnail') AND pm.is_active=TRUE ORDER BY CASE pm.media_type WHEN 'cover' THEN 0 ELSE 1 END, pm.sort_order LIMIT 1) AS cover_storage_type,
                   (SELECT value FROM product_media pm WHERE pm.product_id=p.id AND pm.media_type IN ('cover','thumbnail') AND pm.is_active=TRUE ORDER BY CASE pm.media_type WHEN 'cover' THEN 0 ELSE 1 END, pm.sort_order LIMIT 1) AS cover,
                   (SELECT count(*) FROM product_files pf WHERE pf.product_id=p.id AND pf.is_active=TRUE) AS active_file_count
            FROM products p
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY p.featured DESC,p.sort_order,p.created_at DESC
            """
        ))

    async def get_product(self, conn: asyncpg.Connection, *, product_id: UUID, for_update: bool = False) -> asyncpg.Record | None:
        lock = " FOR UPDATE" if for_update else ""
        return await conn.fetchrow(f"SELECT * FROM products WHERE id=$1{lock}", product_id)

    async def get_by_slug(self, conn: asyncpg.Connection, *, slug: str) -> asyncpg.Record | None:
        return await conn.fetchrow("SELECT * FROM products WHERE slug=$1", slug)

    async def translations(self, conn: asyncpg.Connection, *, product_id: UUID) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            "SELECT * FROM product_translations WHERE product_id=$1 ORDER BY language",
            product_id,
        ))

    async def media(self, conn: asyncpg.Connection, *, product_id: UUID, include_inactive: bool = True) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT * FROM product_media
            WHERE product_id=$1 AND ($2::boolean OR is_active=TRUE)
            ORDER BY is_active DESC,
                     CASE media_type WHEN 'cover' THEN 0 WHEN 'thumbnail' THEN 1 WHEN 'preview' THEN 2 WHEN 'gallery' THEN 3 WHEN 'video' THEN 4 ELSE 5 END,
                     sort_order, created_at
            """,
            product_id,
            include_inactive,
        ))

    async def files(self, conn: asyncpg.Connection, *, product_id: UUID) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            "SELECT * FROM product_files WHERE product_id=$1 ORDER BY is_active DESC, created_at DESC",
            product_id,
        ))

    async def content_blocks(self, conn: asyncpg.Connection, *, product_id: UUID) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT DISTINCT ON (language,block_key,audience_key)
                   id,language,block_key,audience_key,content,version,is_active,created_at,updated_at
            FROM product_content_blocks
            WHERE product_id=$1 AND is_active=TRUE
            ORDER BY language,block_key,audience_key,version DESC
            """,
            product_id,
        ))

    async def relationships(self, conn: asyncpg.Connection, *, product_id: UUID) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT pr.id,pr.target_product_id,pr.relationship_type,pr.sort_order,pr.is_active,
                   target.slug AS target_slug,COALESCE(am.title,en.title,target.slug) AS target_title
            FROM product_relationships pr
            JOIN products target ON target.id=pr.target_product_id
            LEFT JOIN product_translations am ON am.product_id=target.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=target.id AND en.language='en'
            WHERE pr.source_product_id=$1
            ORDER BY pr.is_active DESC,pr.relationship_type,pr.sort_order,target.created_at
            """,
            product_id,
        ))

    async def catalog_choices(self, conn: asyncpg.Connection, *, exclude_product_id: UUID | None = None) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT p.id,p.slug,p.status,COALESCE(am.title,en.title,p.slug) AS title
            FROM products p
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            WHERE ($1::uuid IS NULL OR p.id<>$1)
            ORDER BY p.status='active' DESC,p.featured DESC,p.sort_order,p.created_at DESC
            """,
            exclude_product_id,
        ))

    async def admin_id(self, conn: asyncpg.Connection, *, telegram_id: int) -> UUID | None:
        return await conn.fetchval(
            "SELECT id FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            telegram_id,
        )

    async def insert_audit(
        self,
        conn: asyncpg.Connection,
        *,
        admin_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO audit_logs(actor_type,actor_admin_id,action,entity_type,entity_id,before_data,after_data,metadata)
            VALUES('admin',$1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb)
            """,
            admin_id,
            action,
            entity_type,
            entity_id,
            before,
            after,
            metadata or {"surface": "zemen_control"},
        )
