from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg


class ControlRepository:
    async def overview(self, conn: asyncpg.Connection, *, days: int = 14) -> dict[str, Any]:
        stats = await conn.fetchrow(
            """
            WITH bounds AS (
              SELECT date_trunc(
                'day', now() AT TIME ZONE 'Africa/Addis_Ababa'
              ) AT TIME ZONE 'Africa/Addis_Ababa' AS today_start
            )
            SELECT
              COALESCE((SELECT sum(total_due_br) FROM orders, bounds WHERE status='paid' AND paid_at >= bounds.today_start),0) AS revenue_today_br,
              (SELECT count(*) FROM orders, bounds WHERE status='paid' AND paid_at >= bounds.today_start) AS sales_today,
              (SELECT count(*) FROM users, bounds WHERE status<>'deleted' AND created_at >= bounds.today_start) AS new_users_today,
              COALESCE((SELECT sum(total_due_br) FROM orders WHERE status='paid'),0) AS revenue_lifetime_br,
              (SELECT count(*) FROM users WHERE status<>'deleted') AS users_lifetime,
              (SELECT count(*) FROM payments WHERE status IN ('pending_review','flagged')) AS payments_waiting,
              COALESCE((SELECT sum(total_due_br) FROM orders WHERE status='paid' AND paid_at >= now()-interval '30 days'),0) AS revenue_30d_br,
              (SELECT count(*) FROM orders WHERE status='paid' AND paid_at >= now()-interval '30 days') AS sales_30d,
              (SELECT count(*) FROM orders WHERE status='paid' AND pricing_type='regular' AND paid_at >= now()-interval '30 days') AS full_price_sales_30d,
              (SELECT count(*) FROM orders WHERE status='paid' AND pricing_type<>'regular' AND paid_at >= now()-interval '30 days') AS discount_sales_30d,
              (SELECT count(*) FROM users WHERE created_at >= now()-interval '30 days') AS new_users_30d,
              (SELECT count(*) FROM support_cases WHERE status IN ('open','waiting_admin')) AS support_waiting,
              (SELECT count(*) FROM entitlements WHERE delivery_status='failed') AS deliveries_failed,
              COALESCE((SELECT sum(amount_br) FROM commissions WHERE status IN ('pending','available')),0) AS commission_owed_br
            """
        )
        trend = await conn.fetch(
            """
            WITH bounds AS (
              SELECT (now() AT TIME ZONE 'Africa/Addis_Ababa')::date AS today
            ), days AS (
              SELECT (bounds.today - day_offset)::date AS day
              FROM bounds
              CROSS JOIN generate_series($1 - 1, 0, -1) AS offsets(day_offset)
            ), sales AS (
              SELECT (paid_at AT TIME ZONE 'Africa/Addis_Ababa')::date AS day,
                     count(*) AS sales, sum(total_due_br) AS revenue
              FROM orders, bounds
              WHERE status='paid'
                AND paid_at >= (bounds.today - ($1 - 1)) AT TIME ZONE 'Africa/Addis_Ababa'
              GROUP BY 1
            ), joins AS (
              SELECT (created_at AT TIME ZONE 'Africa/Addis_Ababa')::date AS day,
                     count(*) AS users
              FROM users, bounds
              WHERE status<>'deleted'
                AND created_at >= (bounds.today - ($1 - 1)) AT TIME ZONE 'Africa/Addis_Ababa'
              GROUP BY 1
            )
            SELECT d.day, COALESCE(s.sales,0) AS sales, COALESCE(s.revenue,0) AS revenue,
                   COALESCE(j.users,0) AS users
            FROM days d LEFT JOIN sales s USING(day) LEFT JOIN joins j USING(day)
            ORDER BY d.day
            """,
            max(7, min(days, 90)),
        )
        funnel = await conn.fetchrow(
            """
            SELECT
              count(*) FILTER (WHERE event_type='BOT_STARTED' AND occurred_at >= now()-interval '30 days') AS bot_starts,
              count(*) FILTER (WHERE event_type='PRODUCT_VIEWED' AND occurred_at >= now()-interval '30 days') AS product_views,
              count(*) FILTER (WHERE event_type='BUY_CLICKED' AND occurred_at >= now()-interval '30 days') AS buy_clicks,
              count(*) FILTER (WHERE event_type='PROOF_UPLOADED' AND occurred_at >= now()-interval '30 days') AS proofs,
              count(*) FILTER (WHERE event_type='PURCHASED' AND occurred_at >= now()-interval '30 days') AS purchases
            FROM events
            WHERE occurred_at >= now()-interval '30 days'
            """
        )
        recent = await conn.fetch(
            """
            SELECT o.public_id, o.total_due_br, o.pricing_type, o.paid_at,
                   u.first_name, u.username,
                   COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                   tl.platform, tl.campaign, tl.creative
            FROM orders o
            JOIN users u ON u.id=o.user_id
            JOIN LATERAL (SELECT * FROM order_items WHERE order_id=o.id ORDER BY created_at LIMIT 1) oi ON TRUE
            JOIN products p ON p.id=oi.product_id
            LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=COALESCE(u.preferred_language,'am')
            LEFT JOIN product_translations fallback ON fallback.product_id=p.id AND fallback.language=p.default_language
            LEFT JOIN tracking_links tl ON tl.id=o.source_tracking_link_id
            WHERE o.status='paid'
            ORDER BY o.paid_at DESC NULLS LAST
            LIMIT 8
            """
        )
        result = {k: stats[k] for k in stats.keys()}
        new_users = int(result["new_users_30d"] or 0)
        result["conversion_30d"] = round((int(result["sales_30d"] or 0) / new_users * 100), 2) if new_users else 0.0
        result["range_days"] = max(7, min(days, 90))
        result["trend"] = [dict(r) for r in trend]
        result["funnel"] = {k: int(funnel[k] or 0) for k in funnel.keys()}
        result["recent_sales"] = [dict(r) for r in recent]
        return result

    async def payments(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT p.id, p.public_id, p.status, p.expected_amount_br, p.payment_method,
                   p.latest_proof_id, p.created_at, p.updated_at, p.rejection_reason_code,
                   o.public_id AS order_public_id, o.status AS order_status, o.pricing_type,
                   o.total_due_br, o.discount_total_br,
                   u.id AS user_id, u.telegram_id, u.first_name, u.last_name, u.username,
                   COALESCE(pt.title, fallback.title, pr.slug) AS product_title,
                   pp.created_at AS proof_created_at, pp.proof_status, pp.verifier_data,
                   GREATEST(0, EXTRACT(EPOCH FROM (now()-COALESCE(pp.created_at,p.updated_at))))::bigint AS review_wait_seconds,
                   tl.platform, tl.campaign, tl.creative,
                   ref.username AS referrer_username
            FROM payments p
            JOIN orders o ON o.id=p.order_id
            JOIN users u ON u.id=p.user_id
            JOIN LATERAL (SELECT * FROM order_items WHERE order_id=o.id ORDER BY created_at LIMIT 1) oi ON TRUE
            JOIN products pr ON pr.id=oi.product_id
            LEFT JOIN product_translations pt ON pt.product_id=pr.id AND pt.language=COALESCE(u.preferred_language,'am')
            LEFT JOIN product_translations fallback ON fallback.product_id=pr.id AND fallback.language=pr.default_language
            LEFT JOIN payment_proofs pp ON pp.id=p.latest_proof_id
            LEFT JOIN tracking_links tl ON tl.id=o.source_tracking_link_id
            LEFT JOIN referral_attributions ra ON ra.id=o.referral_attribution_id
            LEFT JOIN users ref ON ref.id=ra.referrer_user_id
            WHERE ($1::text IS NULL OR p.status=$1)
            ORDER BY CASE WHEN p.status IN ('pending_review','flagged') THEN 0 ELSE 1 END,
                     CASE WHEN p.status IN ('pending_review','flagged') THEN COALESCE(pp.created_at,p.updated_at) END ASC NULLS LAST,
                     p.updated_at DESC
            LIMIT $2 OFFSET $3
            """, status, limit, offset))

    async def proof(self, conn: asyncpg.Connection, *, proof_id: UUID) -> asyncpg.Record | None:
        return await conn.fetchrow(
            "SELECT id, telegram_file_id, telegram_media_type, proof_status FROM payment_proofs WHERE id=$1",
            proof_id,
        )

    async def orders(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT o.id, o.public_id, o.status, o.subtotal_br, o.discount_total_br, o.total_due_br,
                   o.pricing_type, o.created_at, o.paid_at, o.expires_at,
                   u.id AS user_id, u.telegram_id, u.first_name, u.username,
                   COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                   tl.platform, tl.campaign, tl.creative,
                   CASE WHEN o.referral_attribution_id IS NOT NULL THEN TRUE ELSE FALSE END AS referred
            FROM orders o
            JOIN users u ON u.id=o.user_id
            JOIN LATERAL (SELECT * FROM order_items WHERE order_id=o.id ORDER BY created_at LIMIT 1) oi ON TRUE
            JOIN products p ON p.id=oi.product_id
            LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=COALESCE(u.preferred_language,'am')
            LEFT JOIN product_translations fallback ON fallback.product_id=p.id AND fallback.language=p.default_language
            LEFT JOIN tracking_links tl ON tl.id=o.source_tracking_link_id
            WHERE ($1::text IS NULL OR o.status=$1)
            ORDER BY o.created_at DESC
            LIMIT $2 OFFSET $3
            """, status, limit, offset))

    async def deliveries(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT e.id, e.delivery_status, e.delivery_attempt_count, e.last_delivery_attempt_at,
                   e.last_delivery_error, e.granted_at, e.delivered_at,
                   u.telegram_id, u.first_name, u.username,
                   o.public_id AS order_public_id,
                   COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                   pf.file_name, pf.version
            FROM entitlements e
            JOIN users u ON u.id=e.user_id
            JOIN products p ON p.id=e.product_id
            JOIN orders o ON o.id=e.granted_by_order_id
            LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=COALESCE(u.preferred_language,'am')
            LEFT JOIN product_translations fallback ON fallback.product_id=p.id AND fallback.language=p.default_language
            LEFT JOIN product_files pf ON pf.id=e.product_file_id
            WHERE ($1::text IS NULL OR e.delivery_status=$1)
            ORDER BY CASE e.delivery_status WHEN 'failed' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                     COALESCE(e.last_delivery_attempt_at,e.granted_at) DESC
            LIMIT $2 OFFSET $3
            """, status, limit, offset))

    async def customers(self, conn: asyncpg.Connection, *, search: str | None, stage: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        needle = f"%{search.strip()}%" if search and search.strip() else None
        return list(await conn.fetch(
            """
            SELECT u.id, u.telegram_id, u.username, u.first_name, u.last_name, u.preferred_language,
                   u.customer_stage, u.created_at, u.last_seen_at, u.is_bot_blocked,
                   up.role, up.ai_experience, up.main_goal, up.main_obstacle,
                   COALESCE((SELECT count(*) FROM entitlements e WHERE e.user_id=u.id AND e.revoked_at IS NULL),0) AS products_owned,
                   COALESCE((SELECT sum(o.total_due_br) FROM orders o WHERE o.user_id=u.id AND o.status='paid'),0) AS lifetime_value_br,
                   COALESCE((SELECT max(j.intent_score) FROM user_product_journeys j WHERE j.user_id=u.id),0) AS max_intent_score
            FROM users u
            LEFT JOIN user_profiles up ON up.user_id=u.id
            WHERE ($1::text IS NULL OR u.customer_stage=$1)
              AND ($2::text IS NULL OR concat_ws(' ',u.first_name,u.last_name,u.username,u.telegram_id::text) ILIKE $2)
            ORDER BY u.last_seen_at DESC
            LIMIT $3 OFFSET $4
            """, stage, needle, limit, offset))

    async def customer_detail(self, conn: asyncpg.Connection, *, user_id: UUID) -> dict[str, Any] | None:
        user = await conn.fetchrow(
            """
            SELECT u.*, up.role, up.ai_experience, up.main_goal, up.main_obstacle, up.onboarding_completed_at
            FROM users u LEFT JOIN user_profiles up ON up.user_id=u.id WHERE u.id=$1
            """, user_id)
        if user is None:
            return None
        journeys = await conn.fetch(
            """
            SELECT j.product_id, j.stage, j.intent_score, j.last_signal_key, j.first_seen_at, j.last_seen_at, j.buy_clicked_at,
                   COALESCE(pt.title, fallback.title, p.slug) AS product_title
            FROM user_product_journeys j JOIN products p ON p.id=j.product_id
            LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=COALESCE($2,'am')
            LEFT JOIN product_translations fallback ON fallback.product_id=p.id AND fallback.language=p.default_language
            WHERE j.user_id=$1 ORDER BY j.last_seen_at DESC
            """, user_id, user["preferred_language"])
        orders = await conn.fetch(
            "SELECT public_id,status,total_due_br,pricing_type,created_at,paid_at FROM orders WHERE user_id=$1 ORDER BY created_at DESC LIMIT 20", user_id)
        events = await conn.fetch(
            "SELECT event_type,payload,occurred_at FROM events WHERE user_id=$1 ORDER BY occurred_at DESC LIMIT 40", user_id)
        source = await conn.fetchrow(
            """
            SELECT us.touch_type, us.created_at, tl.source, tl.platform, tl.campaign, tl.creative, tl.angle
            FROM user_sources us LEFT JOIN tracking_links tl ON tl.id=us.tracking_link_id
            WHERE us.user_id=$1 ORDER BY us.created_at ASC LIMIT 1
            """, user_id)
        referral = await conn.fetchrow(
            """
            SELECT ra.created_at, r.username AS referrer_username, r.first_name AS referrer_name
            FROM referral_attributions ra JOIN users r ON r.id=ra.referrer_user_id
            WHERE ra.referred_user_id=$1 AND ra.status='active'
            """, user_id)
        return {
            "user": dict(user), "journeys": [dict(r) for r in journeys], "orders": [dict(r) for r in orders],
            "events": [dict(r) for r in events], "source": dict(source) if source else None,
            "referral": dict(referral) if referral else None,
        }

    async def products(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT p.id,p.slug,p.status,p.product_type,p.regular_price_br,p.recovery_price_br,
                   p.discounts_enabled,p.referral_enabled,p.referral_commission_percent,p.featured,p.sort_order,
                   COALESCE(am.title,en.title,p.slug) AS title,
                   COALESCE((SELECT count(*) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id AND o.status='paid'),0) AS sales_count,
                   COALESCE((SELECT sum(oi.unit_price_br*oi.quantity) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id AND o.status='paid'),0) AS revenue_br,
                   (SELECT value FROM product_media pm WHERE pm.product_id=p.id AND pm.media_type IN ('cover','thumbnail') AND pm.is_active=TRUE ORDER BY CASE pm.media_type WHEN 'cover' THEN 0 ELSE 1 END, pm.sort_order LIMIT 1) AS cover
            FROM products p
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            ORDER BY p.featured DESC,p.sort_order,p.created_at DESC
            """))

    async def support(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT sc.id,sc.public_id,sc.status,sc.priority,sc.subject,sc.opened_at,sc.updated_at,
                   u.telegram_id,u.first_name,u.username,u.preferred_language,
                   (SELECT sm.body FROM support_messages sm WHERE sm.case_id=sc.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message,
                   (SELECT count(*) FROM support_messages sm WHERE sm.case_id=sc.id) AS message_count
            FROM support_cases sc JOIN users u ON u.id=sc.user_id
            WHERE ($1::text IS NULL OR sc.status=$1)
            ORDER BY CASE sc.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
                     sc.updated_at DESC
            LIMIT $2 OFFSET $3
            """, status, limit, offset))

    async def support_thread(self, conn: asyncpg.Connection, *, case_public_id: str) -> dict[str, Any] | None:
        case = await conn.fetchrow(
            """
            SELECT sc.*,u.telegram_id,u.first_name,u.username,u.preferred_language
            FROM support_cases sc JOIN users u ON u.id=sc.user_id WHERE sc.public_id=$1
            """, case_public_id)
        if case is None:
            return None
        msgs = await conn.fetch(
            """
            SELECT sm.id,sm.sender_type,sm.body,sm.attachment,sm.created_at,
                   au.display_name AS admin_name
            FROM support_messages sm LEFT JOIN admin_users au ON au.id=sm.sender_admin_id
            WHERE sm.case_id=$1 ORDER BY sm.created_at ASC
            """, case["id"])
        return {"case": dict(case), "messages": [dict(r) for r in msgs]}

    async def alerts(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT * FROM operational_alerts
            WHERE ($1::text IS NULL OR status=$1)
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, created_at DESC
            LIMIT $2 OFFSET $3
            """, status, limit, offset))

    async def resolve_alert(self, conn: asyncpg.Connection, *, alert_id: UUID, admin_telegram_id: int) -> bool:
        row = await conn.fetchrow(
            "UPDATE operational_alerts SET status='resolved',resolved_at=now(),updated_at=now(),metadata=metadata || jsonb_build_object('resolved_by_telegram_id',$2::bigint) WHERE id=$1 AND status<>'resolved' RETURNING id",
            alert_id, admin_telegram_id)
        return row is not None
