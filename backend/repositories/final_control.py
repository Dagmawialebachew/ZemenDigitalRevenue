from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg


class FinalControlRepository:
    async def analytics(self, conn: asyncpg.Connection, *, days: int) -> dict[str, Any]:
        summary = await conn.fetchrow(
            """
            WITH bounds AS (SELECT now() - make_interval(days => $1::int) AS since),
            starts AS (
                SELECT count(DISTINCT user_id) AS users
                FROM events,bounds WHERE occurred_at>=since AND event_type='BOT_STARTED' AND user_id IS NOT NULL
            ),
            product_views AS (
                SELECT count(DISTINCT user_id) AS users
                FROM events,bounds WHERE occurred_at>=since AND event_type='PRODUCT_VIEWED' AND user_id IS NOT NULL
            ),
            buy_clicks AS (
                SELECT count(DISTINCT user_id) AS users
                FROM events,bounds WHERE occurred_at>=since AND event_type='BUY_CLICKED' AND user_id IS NOT NULL
            ),
            paid AS (
                SELECT count(*) AS orders, count(DISTINCT user_id) AS buyers,
                       coalesce(sum(total_due_br),0) AS revenue,
                       count(*) FILTER (WHERE pricing_type='regular') AS full_price_orders,
                       count(*) FILTER (WHERE pricing_type<>'regular') AS discounted_orders
                FROM orders,bounds WHERE status='paid' AND paid_at>=since
            )
            SELECT starts.users AS started_users, product_views.users AS product_view_users,
                   buy_clicks.users AS buy_click_users, paid.orders AS paid_orders,
                   paid.buyers AS buyers, paid.revenue AS revenue_br,
                   paid.full_price_orders, paid.discounted_orders
            FROM starts,product_views,buy_clicks,paid
            """,
            days,
        )
        funnel = await conn.fetch(
            """
            WITH bounds AS (SELECT now() - make_interval(days => $1::int) AS since),
            stages(stage,sort,event_type) AS (VALUES
                ('Bot Started',1,'BOT_STARTED'),
                ('Onboarding Complete',2,'ONBOARDING_COMPLETED'),
                ('Product Viewed',3,'PRODUCT_VIEWED'),
                ('Buy Clicked',4,'BUY_CLICKED'),
                ('Proof Uploaded',5,'PROOF_UPLOADED'),
                ('Purchased',6,'PURCHASED')
            )
            SELECT s.stage,s.sort,count(DISTINCT e.user_id)::int AS users
            FROM stages s
            LEFT JOIN events e ON e.event_type=s.event_type
                AND e.occurred_at >= (SELECT since FROM bounds)
                AND e.user_id IS NOT NULL
            GROUP BY s.stage,s.sort ORDER BY s.sort
            """,
            days,
        )
        series = await conn.fetch(
            """
            WITH days AS (
                SELECT generate_series(current_date-($1::int-1),current_date,'1 day'::interval)::date AS day
            ), paid AS (
                SELECT paid_at::date AS day,count(*)::int AS sales,coalesce(sum(total_due_br),0) AS revenue
                FROM orders WHERE status='paid' AND paid_at>=current_date-($1::int-1)
                GROUP BY paid_at::date
            ), users AS (
                SELECT created_at::date AS day,count(*)::int AS users FROM users
                WHERE created_at>=current_date-($1::int-1) GROUP BY created_at::date
            )
            SELECT d.day,coalesce(p.sales,0) AS sales,coalesce(p.revenue,0) AS revenue_br,
                   coalesce(u.users,0) AS new_users
            FROM days d LEFT JOIN paid p USING(day) LEFT JOIN users u USING(day) ORDER BY d.day
            """,
            days,
        )
        # Aggregate sales and attention independently before joining them to the
        # product row. Joining raw orders and raw events together would multiply
        # rows (views × orders) and inflate revenue.
        products = await conn.fetch(
            """
            SELECT p.id,p.slug,coalesce(am.title,en.title,p.slug) AS title,
                   coalesce(s.paid_orders,0)::int AS paid_orders,
                   coalesce(s.full_price_orders,0)::int AS full_price_orders,
                   coalesce(s.discounted_orders,0)::int AS discounted_orders,
                   coalesce(s.revenue_br,0) AS revenue_br,
                   coalesce(v.viewers,0)::int AS viewers
            FROM products p
            LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
            LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
            LEFT JOIN LATERAL (
                SELECT count(DISTINCT o.id) AS paid_orders,
                       count(DISTINCT o.id) FILTER (WHERE o.pricing_type='regular') AS full_price_orders,
                       count(DISTINCT o.id) FILTER (WHERE o.pricing_type<>'regular') AS discounted_orders,
                       coalesce(sum(oi.unit_price_br * oi.quantity),0) AS revenue_br
                FROM order_items oi
                JOIN orders o ON o.id=oi.order_id
                WHERE oi.product_id=p.id AND o.status='paid'
                  AND o.paid_at>=now()-make_interval(days=>$1::int)
            ) s ON TRUE
            LEFT JOIN LATERAL (
                SELECT count(DISTINCT e.user_id) AS viewers
                FROM events e
                WHERE e.product_id=p.id AND e.event_type='PRODUCT_VIEWED'
                  AND e.user_id IS NOT NULL
                  AND e.occurred_at>=now()-make_interval(days=>$1::int)
            ) v ON TRUE
            ORDER BY revenue_br DESC,p.created_at DESC
            """,
            days,
        )
        # Same rule for source attribution: starts and purchases are separate
        # aggregates so multiple source touches cannot multiply paid revenue.
        sources = await conn.fetch(
            """
            SELECT tl.id,coalesce(tl.label,tl.creative,tl.campaign,tl.source) AS label,
                   tl.source,tl.platform,tl.campaign,tl.ad_set,tl.creative,tl.angle,
                   coalesce(st.starts,0)::int AS starts,
                   coalesce(pa.purchases,0)::int AS purchases,
                   coalesce(pa.revenue_br,0) AS revenue_br
            FROM tracking_links tl
            LEFT JOIN LATERAL (
                SELECT count(DISTINCT us.user_id) AS starts
                FROM user_sources us
                WHERE us.tracking_link_id=tl.id
                  AND us.created_at>=now()-make_interval(days=>$1::int)
            ) st ON TRUE
            LEFT JOIN LATERAL (
                SELECT count(*) AS purchases,coalesce(sum(o.total_due_br),0) AS revenue_br
                FROM orders o
                WHERE o.source_tracking_link_id=tl.id AND o.status='paid'
                  AND o.paid_at>=now()-make_interval(days=>$1::int)
            ) pa ON TRUE
            ORDER BY revenue_br DESC,starts DESC LIMIT 100
            """,
            days,
        )
        audiences = await conn.fetch(
            """
            SELECT coalesce(u.preferred_language,'unknown') AS dimension,'language' AS kind,
                   count(DISTINCT u.id)::int AS users,
                   count(DISTINCT o.id)::int AS paid_orders,
                   coalesce(sum(o.total_due_br),0) AS revenue_br
            FROM users u LEFT JOIN orders o ON o.user_id=u.id AND o.status='paid' AND o.paid_at>=now()-make_interval(days=>$1::int)
            WHERE u.created_at>=now()-make_interval(days=>$1::int)
            GROUP BY coalesce(u.preferred_language,'unknown')
            UNION ALL
            SELECT coalesce(up.role,'unknown'),'role',count(DISTINCT u.id)::int,count(DISTINCT o.id)::int,coalesce(sum(o.total_due_br),0)
            FROM users u LEFT JOIN user_profiles up ON up.user_id=u.id
            LEFT JOIN orders o ON o.user_id=u.id AND o.status='paid' AND o.paid_at>=now()-make_interval(days=>$1::int)
            WHERE u.created_at>=now()-make_interval(days=>$1::int)
            GROUP BY coalesce(up.role,'unknown')
            ORDER BY kind,paid_orders DESC,users DESC
            """,
            days,
        )
        time_to_purchase = await conn.fetchrow(
            """
            WITH first_seen AS (
                SELECT id AS user_id,created_at FROM users WHERE created_at>=now()-make_interval(days=>$1::int)
            ), first_paid AS (
                SELECT user_id,min(paid_at) AS paid_at FROM orders WHERE status='paid' GROUP BY user_id
            )
            SELECT count(*)::int AS buyers,
                   round(avg(extract(epoch FROM (p.paid_at-f.created_at))/3600)::numeric,1) AS avg_hours,
                   round(percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM (p.paid_at-f.created_at))/3600)::numeric,1) AS median_hours
            FROM first_seen f JOIN first_paid p USING(user_id) WHERE p.paid_at>=f.created_at
            """,
            days,
        )
        return {
            "days": days,
            "summary": dict(summary or {}),
            "funnel": [dict(r) for r in funnel],
            "series": [dict(r) for r in series],
            "products": [dict(r) for r in products],
            "sources": [dict(r) for r in sources],
            "audiences": [dict(r) for r in audiences],
            "time_to_purchase": dict(time_to_purchase or {}),
        }

    async def financials(self, conn: asyncpg.Connection, *, days: int) -> dict[str, Any]:
        summary = await conn.fetchrow(
            """
            WITH bounds AS (SELECT now()-make_interval(days=>$1::int) AS since),
            revenue AS (
                SELECT coalesce(sum(total_due_br),0) AS gross,
                       coalesce(sum(total_due_br) FILTER (WHERE pricing_type='regular'),0) AS full_price,
                       coalesce(sum(total_due_br) FILTER (WHERE pricing_type<>'regular'),0) AS discounted,
                       count(*)::int AS sales
                FROM orders,bounds WHERE status IN ('paid','refunded') AND paid_at>=since
            ), refunds AS (
                SELECT coalesce(sum(total_due_br),0) AS amount,count(*)::int AS count
                FROM orders,bounds WHERE status='refunded' AND updated_at>=since
            ), expenses AS (
                SELECT coalesce(sum(amount_br),0) AS amount FROM business_expenses
                WHERE expense_date>=current_date-($1::int-1)
            ), commissions AS (
                SELECT coalesce(sum(amount_br) FILTER (WHERE status='paid' AND paid_at>=now()-make_interval(days=>$1::int)),0) AS paid,
                       coalesce(sum(amount_br) FILTER (WHERE status IN ('pending','available')),0) AS owed
                FROM commissions
            )
            SELECT revenue.gross AS gross_revenue_br,revenue.full_price AS full_price_revenue_br,
                   revenue.discounted AS discounted_revenue_br,revenue.sales,
                   refunds.amount AS refunds_br,refunds.count AS refund_count,
                   expenses.amount AS recorded_expenses_br,commissions.paid AS paid_commissions_br,
                   commissions.owed AS commission_owed_br
            FROM revenue,refunds,expenses,commissions
            """,
            days,
        )
        daily = await conn.fetch(
    """
    WITH d AS (
        SELECT generate_series(
            current_date - ($1::int - 1),
            current_date,
            INTERVAL '1 day'
        )::date AS report_date
    ),
    r AS (
        SELECT
            paid_at::date AS report_date,
            COALESCE(SUM(total_due_br), 0) AS revenue
        FROM orders
        WHERE status IN ('paid', 'refunded')
          AND paid_at >= current_date - ($1::int - 1)
        GROUP BY paid_at::date
    ),
    e AS (
        SELECT
            expense_date AS report_date,
            COALESCE(SUM(amount_br), 0) AS expenses
        FROM business_expenses
        WHERE expense_date >= current_date - ($1::int - 1)
        GROUP BY expense_date
    ),
    c AS (
        SELECT
            paid_at::date AS report_date,
            COALESCE(SUM(amount_br), 0) AS commissions
        FROM commissions
        WHERE status = 'paid'
          AND paid_at >= current_date - ($1::int - 1)
        GROUP BY paid_at::date
    )
    SELECT
        d.report_date AS day,
        COALESCE(r.revenue, 0) AS revenue_br,
        COALESCE(e.expenses, 0) AS expenses_br,
        COALESCE(c.commissions, 0) AS commissions_paid_br
    FROM d
    LEFT JOIN r USING (report_date)
    LEFT JOIN e USING (report_date)
    LEFT JOIN c USING (report_date)
    ORDER BY d.report_date
    """,
    days,
)
        
        expenses = await conn.fetch(
            """SELECT be.*,au.display_name AS created_by FROM business_expenses be
               LEFT JOIN admin_users au ON au.id=be.created_by_admin_id
               ORDER BY expense_date DESC,created_at DESC LIMIT 250"""
        )
        commission_rows = await conn.fetch(
            """SELECT c.status,count(*)::int AS count,coalesce(sum(c.amount_br),0) AS amount_br
               FROM commissions c GROUP BY c.status ORDER BY c.status"""
        )
        payment_methods = await conn.fetch(
            """SELECT p.payment_method,count(*)::int AS payments,coalesce(sum(p.expected_amount_br),0) AS amount_br
               FROM payments p WHERE p.status='approved' AND p.approved_at>=now()-make_interval(days=>$1::int)
               GROUP BY p.payment_method ORDER BY amount_br DESC""",
            days,
        )
        return {
            "days": days,
            "summary": dict(summary or {}),
            "daily": [dict(r) for r in daily],
            "expenses": [dict(r) for r in expenses],
            "commissions": [dict(r) for r in commission_rows],
            "payment_methods": [dict(r) for r in payment_methods],
        }

    async def create_expense(
        self,
        conn: asyncpg.Connection,
        *,
        expense_date: date,
        category: str,
        amount_br: Any,
        description: str,
        reference: str | None,
        admin_id: UUID | None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """INSERT INTO business_expenses(expense_date,category,amount_br,description,reference,created_by_admin_id)
               VALUES($1,$2,$3,$4,$5,$6) RETURNING *""",
            expense_date, category, amount_br, description, reference, admin_id,
        )

    async def delete_expense(self, conn: asyncpg.Connection, *, expense_id: UUID) -> asyncpg.Record | None:
        return await conn.fetchrow("DELETE FROM business_expenses WHERE id=$1 RETURNING *", expense_id)

    async def reviews(self, conn: asyncpg.Connection, *, status: str | None, limit: int, offset: int) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """
            SELECT r.id,r.rating,r.review_text,r.language,r.status,r.featured,r.verified_purchase,r.source,
                   r.created_at,r.updated_at,r.moderated_at,
                   u.telegram_id,u.first_name,u.username,
                   p.id AS product_id,coalesce(pt.title,fb.title,p.slug) AS product_title,
                   o.public_id AS order_public_id,au.display_name AS moderated_by
            FROM reviews r JOIN users u ON u.id=r.user_id JOIN products p ON p.id=r.product_id
            LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=coalesce(r.language,'am')
            LEFT JOIN product_translations fb ON fb.product_id=p.id AND fb.language=p.default_language
            LEFT JOIN orders o ON o.id=r.order_id
            LEFT JOIN admin_users au ON au.id=r.moderated_by_admin_id
            WHERE ($1::text IS NULL OR r.status=$1)
            ORDER BY CASE r.status WHEN 'pending' THEN 0 ELSE 1 END,r.created_at DESC
            LIMIT $2 OFFSET $3
            """,
            status, limit, offset,
        ))

    async def moderate_review(
        self,
        conn: asyncpg.Connection,
        *,
        review_id: UUID,
        new_status: str,
        featured: bool,
        admin_id: UUID | None,
    ) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """UPDATE reviews SET status=$2,featured=$3,moderated_by_admin_id=$4,moderated_at=now(),updated_at=now()
               WHERE id=$1 RETURNING *""",
            review_id, new_status, featured if new_status == "approved" else False, admin_id,
        )

    async def settings(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """SELECT s.key,s.value,s.description,s.updated_at,au.display_name AS updated_by
               FROM settings s LEFT JOIN admin_users au ON au.id=s.updated_by_admin_id
               WHERE s.key LIKE 'business.%' OR s.key LIKE 'referrals.%' OR s.key LIKE 'reviews.%'
               ORDER BY s.key"""
        ))

    async def set_setting(self, conn: asyncpg.Connection, *, key: str, value: Any, admin_id: UUID | None) -> asyncpg.Record:
        return await conn.fetchrow(
            """INSERT INTO settings(key,value,updated_by_admin_id,updated_at)
               VALUES($1,$2::jsonb,$3,now())
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_by_admin_id=excluded.updated_by_admin_id,updated_at=now()
               RETURNING *""",
            key, value, admin_id,
        )

    async def admins(self, conn: asyncpg.Connection) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            "SELECT id,telegram_id,email,display_name,role,is_active,created_at,updated_at FROM admin_users ORDER BY is_active DESC,role,display_name"
        ))

    async def upsert_admin(self, conn: asyncpg.Connection, *, telegram_id: int, display_name: str, role: str) -> asyncpg.Record:
        return await conn.fetchrow(
            """INSERT INTO admin_users(telegram_id,display_name,role,is_active)
               VALUES($1,$2,$3,TRUE)
               ON CONFLICT(telegram_id) DO UPDATE SET display_name=excluded.display_name,role=excluded.role,is_active=TRUE,updated_at=now()
               RETURNING id,telegram_id,email,display_name,role,is_active,created_at,updated_at""",
            telegram_id, display_name, role,
        )

    async def set_admin_active(self, conn: asyncpg.Connection, *, admin_id: UUID, active: bool) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """UPDATE admin_users SET is_active=$2,updated_at=now() WHERE id=$1
               RETURNING id,telegram_id,email,display_name,role,is_active,created_at,updated_at""",
            admin_id, active,
        )

    async def audit(self, conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
        return list(await conn.fetch(
            """SELECT al.id,al.action,al.entity_type,al.entity_id,al.metadata,al.created_at,
                      au.display_name AS admin_name,u.first_name AS user_name
               FROM audit_logs al
               LEFT JOIN admin_users au ON au.id=al.actor_admin_id
               LEFT JOIN users u ON u.id=al.actor_user_id
               ORDER BY al.created_at DESC LIMIT $1""",
            limit,
        ))
