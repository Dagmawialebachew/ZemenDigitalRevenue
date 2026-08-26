from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from backend.domain.marketing import Audience


class MarketingRepository:
    async def admin_id(self, conn: asyncpg.Connection, telegram_id: int) -> UUID | None:
        return await conn.fetchval(
            "SELECT id FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            telegram_id,
        )

    async def audit(
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
            metadata or {"surface": "zemen_control", "section": "marketing"},
        )

    async def product_choices(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT p.id,p.slug,p.status,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,
                   COALESCE(am.title,en.title,p.slug) AS title
            FROM products p
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY p.status='active' DESC,p.featured DESC,p.sort_order,p.created_at DESC
            """
        ))

    def _audience_sql(self, audience: Audience, *, select: str, user_id: Any | None = None) -> tuple[str, list[Any]]:
        # Keep segmentation as a fixed SQL grammar; dashboard values never become SQL identifiers.
        args: list[Any] = [
            audience.kind,
            audience.language,
            audience.stage,
            audience.product_id,
            audience.tracking_link_id,
            audience.minimum_intent_score,
            user_id,
        ]
        sql = f"""
        SELECT {select}
        FROM users u
        WHERE u.status='active' AND u.is_bot_blocked=FALSE
          AND ($7::uuid IS NULL OR u.id=$7::uuid)
          AND ($2::text IS NULL OR COALESCE(u.preferred_language,'am')=$2)
          AND ($3::text IS NULL OR u.customer_stage=$3)
          AND (
            $5::uuid IS NULL OR EXISTS (
              SELECT 1 FROM user_sources us
              WHERE us.user_id=u.id AND us.tracking_link_id=$5::uuid
            )
          )
          AND (
            $6::int IS NULL OR EXISTS (
              SELECT 1 FROM user_product_journeys j
              WHERE j.user_id=u.id
                AND ($4::uuid IS NULL OR j.product_id=$4::uuid)
                AND j.intent_score >= $6::int
            )
          )
          AND (
            $1='everyone'
            OR $1='custom'
            OR ($1='non_buyers' AND NOT EXISTS (
                SELECT 1 FROM orders o
                WHERE o.user_id=u.id AND o.status='paid'
                  AND ($4::uuid IS NULL OR EXISTS (
                    SELECT 1 FROM order_items oi WHERE oi.order_id=o.id AND oi.product_id=$4::uuid
                  ))
            ))
            OR ($1='customers' AND EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.id AND o.status='paid'))
            OR ($1='product_buyers' AND EXISTS (
                SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                WHERE o.user_id=u.id AND o.status='paid' AND oi.product_id=$4::uuid
            ))
            OR ($1='full_price_buyers' AND EXISTS (
                SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                WHERE o.user_id=u.id AND o.status='paid' AND oi.product_id=$4::uuid
                  AND o.pricing_type='regular' AND o.discount_total_br=0
            ))
            OR ($1='discount_buyers' AND EXISTS (
                SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                WHERE o.user_id=u.id AND o.status='paid' AND oi.product_id=$4::uuid
                  AND (o.pricing_type<>'regular' OR o.discount_total_br>0)
            ))
            OR ($1='referral_partners' AND EXISTS (
                SELECT 1 FROM referral_accounts ra WHERE ra.owner_user_id=u.id AND ra.is_active=TRUE
            ))
            OR ($1='rejected_payment' AND EXISTS (
                SELECT 1 FROM payments p WHERE p.user_id=u.id AND p.status='rejected'
            ))
            OR ($1='high_intent' AND EXISTS (
                SELECT 1 FROM user_product_journeys j WHERE j.user_id=u.id AND j.product_id=$4::uuid AND j.stage='high_intent'
            ))
          )
        """
        return sql, args

    async def audience_count(self, conn: asyncpg.Connection, audience: Audience) -> int:
        sql, args = self._audience_sql(audience, select="count(*)")
        return int(await conn.fetchval(sql, *args) or 0)


    async def user_matches_audience(self, conn: asyncpg.Connection, *, user_id: Any, audience: Audience) -> bool:
        sql, args = self._audience_sql(audience, select="count(*)", user_id=user_id)
        return int(await conn.fetchval(sql, *args) or 0) > 0

    async def audience_users(self, conn: asyncpg.Connection, audience: Audience) -> list[asyncpg.Record]:
        select = "u.id AS user_id,u.telegram_id,COALESCE(u.preferred_language,'am') AS language,u.first_name,u.username"
        sql, args = self._audience_sql(audience, select=select)
        return list(await conn.fetch(sql + " ORDER BY u.created_at ASC", *args))

    async def snapshot_broadcast_audience(self, conn: asyncpg.Connection, *, broadcast_id: UUID, audience: Audience) -> int:
        """Freeze the audience in PostgreSQL without loading every recipient into app memory."""
        select = "u.id AS user_id,CASE WHEN u.preferred_language='en' THEN 'en' ELSE 'am' END AS language"
        audience_sql, args = self._audience_sql(audience, select=select)
        command = await conn.execute(
            f"""
            INSERT INTO broadcast_recipients(broadcast_id,user_id,status,language)
            SELECT $8::uuid,q.user_id,'queued',q.language
            FROM ({audience_sql}) q
            """,
            *args, broadcast_id,
        )
        return int(command.rsplit(" ", 1)[-1])

    async def overview(self, conn: asyncpg.Connection) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT
              (SELECT count(*) FROM broadcasts WHERE status IN ('scheduled','sending')) AS active_broadcasts,
              (SELECT count(*) FROM automations WHERE is_enabled=TRUE) AS active_automations,
              (SELECT count(*) FROM customer_offers WHERE status='available' AND (expires_at IS NULL OR expires_at>now())) AS live_offers,
              (SELECT count(*) FROM tracking_links WHERE is_active=TRUE) AS active_ad_links,
              COALESCE((SELECT sum(amount_br) FROM commissions WHERE status IN ('pending','available')),0) AS commission_owed_br,
              COALESCE((SELECT sum(c.amount_br) FROM commissions c WHERE c.status='available' AND NOT EXISTS (SELECT 1 FROM commission_payout_items cpi WHERE cpi.commission_id=c.id)),0) AS commission_available_br,
              (SELECT count(DISTINCT owner_user_id) FROM referral_accounts WHERE is_active=TRUE) AS referral_partners,
              (SELECT count(*) FROM broadcasts WHERE status='sent' AND completed_at>=now()-interval '30 days') AS broadcasts_30d,
              COALESCE((SELECT sum(o.total_due_br)
                 FROM orders o WHERE o.id IN (
                   SELECT DISTINCT converted_order_id FROM broadcast_recipients WHERE converted_order_id IS NOT NULL
                 ) AND o.status='paid' AND o.paid_at>=now()-interval '30 days'),0) AS broadcast_revenue_30d_br
            """
        )
        return dict(row)

    async def list_broadcasts(self, conn: asyncpg.Connection, limit: int = 100) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT b.*,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id),0) AS recipients,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id AND br.status='sent'),0) AS sent_count,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id AND br.status='blocked'),0) AS blocked_count,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id AND br.status='failed'),0) AS failed_count,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id AND br.clicked_at IS NOT NULL),0) AS clickers,
              COALESCE((SELECT count(*) FROM broadcast_recipients br WHERE br.broadcast_id=b.id AND br.converted_order_id IS NOT NULL),0) AS conversions,
              COALESCE((SELECT sum(o.total_due_br) FROM broadcast_recipients br JOIN orders o ON o.id=br.converted_order_id WHERE br.broadcast_id=b.id AND o.status='paid'),0) AS revenue_br
            FROM broadcasts b
            ORDER BY b.created_at DESC LIMIT $1
            """,
            limit,
        ))

    async def broadcast(self, conn: asyncpg.Connection, broadcast_id: UUID, for_update: bool = False) -> asyncpg.Record | None:
        lock = " FOR UPDATE" if for_update else ""
        return await conn.fetchrow(f"SELECT * FROM broadcasts WHERE id=$1{lock}", broadcast_id)

    async def automation(self, conn: asyncpg.Connection, automation_id: UUID, for_update: bool = False) -> asyncpg.Record | None:
        lock = " FOR UPDATE" if for_update else ""
        return await conn.fetchrow(f"SELECT * FROM automations WHERE id=$1{lock}", automation_id)

    async def list_automations(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT a.*,COALESCE(am.title,en.title,p.slug) AS product_title,
              (SELECT count(*) FROM automation_steps s WHERE s.automation_id=a.id) AS step_count,
              (SELECT count(*) FROM automation_runs r WHERE r.automation_id=a.id AND r.status IN ('active','waiting')) AS active_runs,
              (SELECT count(*) FROM automation_runs r WHERE r.automation_id=a.id AND r.started_at>=now()-interval '30 days') AS runs_30d
            FROM automations a
            LEFT JOIN products p ON p.id=a.product_id
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY a.is_enabled DESC,a.updated_at DESC
            """
        ))

    async def automation_steps(self, conn: asyncpg.Connection, automation_id: UUID) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            "SELECT * FROM automation_steps WHERE automation_id=$1 ORDER BY sort_order",
            automation_id,
        ))

    async def list_discount_rules(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT dr.*,COALESCE(am.title,en.title,p.slug) AS product_title,p.regular_price_br,p.recovery_price_br,
              (SELECT count(*) FROM customer_offers co WHERE co.discount_rule_id=dr.id AND co.status='available') AS live_offers,
              (SELECT count(*) FROM customer_offers co WHERE co.discount_rule_id=dr.id AND co.status='redeemed') AS redeemed_offers
            FROM discount_rules dr JOIN products p ON p.id=dr.product_id
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY dr.is_active DESC,dr.updated_at DESC
            """
        ))

    async def list_offers(self, conn: asyncpg.Connection, limit: int = 100) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT co.*,u.telegram_id,u.first_name,u.username,COALESCE(am.title,en.title,p.slug) AS product_title,
                   dr.name AS rule_name
            FROM customer_offers co
            JOIN users u ON u.id=co.user_id JOIN products p ON p.id=co.product_id
            LEFT JOIN discount_rules dr ON dr.id=co.discount_rule_id
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY co.created_at DESC LIMIT $1
            """,
            limit,
        ))

    async def list_links(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT tl.*,COALESCE(am.title,en.title,p.slug) AS product_title,
              (SELECT count(*) FROM user_sources us WHERE us.tracking_link_id=tl.id) AS starts,
              (SELECT count(DISTINCT o.id) FROM orders o WHERE o.source_tracking_link_id=tl.id AND o.status='paid') AS purchases,
              COALESCE((SELECT sum(o.total_due_br) FROM orders o WHERE o.source_tracking_link_id=tl.id AND o.status='paid'),0) AS revenue_br
            FROM tracking_links tl
            LEFT JOIN products p ON p.id=tl.product_id
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY tl.created_at DESC
            """
        ))

    async def referral_summary(self, conn: asyncpg.Connection) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT
              (SELECT count(*) FROM referral_accounts WHERE is_active=TRUE) AS partners,
              (SELECT count(*) FROM referral_attributions WHERE status='active') AS referred_users,
              (SELECT count(*) FROM commissions) AS commission_sales,
              COALESCE((SELECT sum(amount_br) FROM commissions WHERE status IN ('pending','available')),0) AS owed_br,
              COALESCE((SELECT sum(c.amount_br) FROM commissions c WHERE c.status='available'
                  AND NOT EXISTS (SELECT 1 FROM commission_payout_items i WHERE i.commission_id=c.id)),0) AS available_br,
              COALESCE((SELECT sum(amount_br) FROM commissions WHERE status='paid'),0) AS paid_br
            """
        )
        return dict(row)

    async def referral_partners(self, conn: asyncpg.Connection, limit: int = 200) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT ra.id,ra.code,ra.is_active,ra.created_at,u.id AS user_id,u.telegram_id,u.first_name,u.username,
              rp.payout_method,rp.payout_destination,rp.account_name,
              (SELECT count(*) FROM referral_attributions a WHERE a.referrer_user_id=u.id AND a.status='active') AS joins,
              (SELECT count(*) FROM commissions c WHERE c.referrer_user_id=u.id) AS paid_referrals,
              COALESCE((SELECT sum(amount_br) FROM commissions c WHERE c.referrer_user_id=u.id AND c.status IN ('pending','available')),0) AS owed_br,
              COALESCE((SELECT sum(c.amount_br) FROM commissions c WHERE c.referrer_user_id=u.id AND c.status='available'
                  AND NOT EXISTS (SELECT 1 FROM commission_payout_items i WHERE i.commission_id=c.id)),0) AS available_br,
              COALESCE((SELECT sum(amount_br) FROM commissions c WHERE c.referrer_user_id=u.id AND c.status='paid'),0) AS paid_br
            FROM referral_accounts ra JOIN users u ON u.id=ra.owner_user_id
            LEFT JOIN referral_payout_profiles rp ON rp.user_id=u.id
            ORDER BY available_br DESC,joins DESC,ra.created_at DESC LIMIT $1
            """,
            limit,
        ))

    async def payouts(self, conn: asyncpg.Connection, limit: int = 200) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT cp.*,u.telegram_id,u.first_name,u.username,
              (SELECT count(*) FROM commission_payout_items i WHERE i.payout_id=cp.id) AS commission_count
            FROM commission_payouts cp JOIN users u ON u.id=cp.referrer_user_id
            ORDER BY cp.created_at DESC LIMIT $1
            """,
            limit,
        ))

    async def bulk_create_campaign_offers(
        self,
        conn: asyncpg.Connection,
        *,
        discount_rule_id: UUID,
        product_id: UUID,
        original_price_br: Any,
        offer_price_br: Any,
        expires_at: Any,
    ) -> int:
        """Bulk-insert customer_offers for all non-buyer, non-blocked, active users who don't already have an active/available offer for this product."""
        command = await conn.execute(
            """
            INSERT INTO customer_offers(user_id,product_id,discount_rule_id,original_price_br,offer_price_br,status,eligible_at,starts_at,expires_at)
            SELECT u.id,$1,$2,$3,$4,'available',now(),now(),$5
            FROM users u
            WHERE u.status='active' AND u.is_bot_blocked=FALSE
              AND NOT EXISTS (
                SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                WHERE o.user_id=u.id AND oi.product_id=$1 AND o.status='paid'
              )
              AND NOT EXISTS (
                SELECT 1 FROM customer_offers co
                WHERE co.user_id=u.id AND co.product_id=$1
                  AND co.status IN ('scheduled','available')
              )
            """,
            product_id, discount_rule_id, original_price_br, offer_price_br, expires_at,
        )
        return int(command.rsplit(" ", 1)[-1])
