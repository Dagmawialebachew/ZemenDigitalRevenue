from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg


class OperationsRepository:
    async def overview(self, conn: asyncpg.Connection) -> dict[str, int]:
        row = await conn.fetchrow(
            """
            SELECT
              (SELECT count(*) FROM payments WHERE status IN ('pending_review','flagged')) AS payments_waiting,
              (SELECT count(*) FROM entitlements WHERE delivery_status='failed') AS deliveries_failed,
              (SELECT count(*) FROM entitlements WHERE delivery_status IN ('pending','queued')) AS deliveries_waiting,
              (SELECT count(*) FROM support_cases WHERE status IN ('open','waiting_admin')) AS support_waiting,
              (SELECT count(*) FROM operational_alerts WHERE status='open') AS alerts_open,
              (SELECT count(*) FROM jobs WHERE status='failed') AS jobs_failed
            """
        )
        return {key: int(row[key] or 0) for key in row.keys()}

    async def payment_queue(self, conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT p.id, p.public_id, p.status, p.expected_amount_br, p.payment_method,
                       p.updated_at, p.latest_proof_id,
                       o.public_id AS order_public_id, o.total_due_br, o.pricing_type,
                       u.telegram_id, u.first_name, u.username,
                       COALESCE(pt.title, fallback.title, pr.slug) AS product_title
                FROM payments p
                JOIN orders o ON o.id=p.order_id
                JOIN users u ON u.id=p.user_id
                JOIN order_items oi ON oi.order_id=o.id
                JOIN products pr ON pr.id=oi.product_id
                LEFT JOIN product_translations pt ON pt.product_id=pr.id AND pt.language=COALESCE(u.preferred_language,'am')
                LEFT JOIN product_translations fallback ON fallback.product_id=pr.id AND fallback.language=pr.default_language
                WHERE p.status IN ('pending_review','flagged')
                ORDER BY p.updated_at ASC
                LIMIT $1
                """,
                limit,
            )
        )

    async def delivery_queue(self, conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT e.id, e.delivery_status, e.delivery_attempt_count, e.last_delivery_attempt_at,
                       e.last_delivery_error, e.granted_at, e.delivered_at,
                       u.telegram_id, u.first_name, u.username,
                       o.public_id AS order_public_id,
                       COALESCE(pt.title, fallback.title, p.slug) AS product_title,
                       pf.telegram_file_id, pf.version
                FROM entitlements e
                JOIN users u ON u.id=e.user_id
                JOIN products p ON p.id=e.product_id
                JOIN orders o ON o.id=e.granted_by_order_id
                LEFT JOIN product_translations pt ON pt.product_id=p.id AND pt.language=COALESCE(u.preferred_language,'am')
                LEFT JOIN product_translations fallback ON fallback.product_id=p.id AND fallback.language=p.default_language
                LEFT JOIN product_files pf ON pf.id=e.product_file_id
                WHERE e.delivery_status IN ('pending','queued','failed')
                ORDER BY CASE e.delivery_status WHEN 'failed' THEN 0 ELSE 1 END,
                         COALESCE(e.last_delivery_attempt_at, e.granted_at) ASC
                LIMIT $1
                """,
                limit,
            )
        )

    async def support_queue(self, conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT sc.*, u.telegram_id, u.first_name, u.username, u.preferred_language,
                       (SELECT body FROM support_messages sm WHERE sm.case_id=sc.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message
                FROM support_cases sc
                JOIN users u ON u.id=sc.user_id
                WHERE sc.status IN ('open','waiting_admin','waiting_customer')
                ORDER BY CASE sc.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                         sc.updated_at ASC
                LIMIT $1
                """,
                limit,
            )
        )

    async def alerts(self, conn: asyncpg.Connection, *, limit: int = 100) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT * FROM operational_alerts
                WHERE status <> 'resolved'
                ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                         created_at DESC
                LIMIT $1
                """,
                limit,
            )
        )

    async def upsert_alert(
        self,
        conn: asyncpg.Connection,
        *,
        alert_key: str,
        severity: str,
        alert_type: str,
        title: str,
        body: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> asyncpg.Record:
        return await conn.fetchrow(
            """
            INSERT INTO operational_alerts (
                alert_key, severity, alert_type, title, body, entity_type, entity_id, metadata
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
            ON CONFLICT (alert_key) DO UPDATE SET
                severity=EXCLUDED.severity,
                title=EXCLUDED.title,
                body=EXCLUDED.body,
                metadata=operational_alerts.metadata || EXCLUDED.metadata,
                status=CASE WHEN operational_alerts.status='resolved' THEN 'open' ELSE operational_alerts.status END,
                resolved_at=CASE WHEN operational_alerts.status='resolved' THEN NULL ELSE operational_alerts.resolved_at END,
                updated_at=now()
            RETURNING *
            """,
            alert_key,
            severity,
            alert_type,
            title,
            body,
            entity_type,
            entity_id,
            metadata or {},
        )

    async def record_alert_message(
        self, conn: asyncpg.Connection, *, alert_id: UUID, chat_id: int, message_id: int
    ) -> None:
        await conn.execute(
            "UPDATE operational_alerts SET ops_chat_id=$2, ops_message_id=$3, updated_at=now() WHERE id=$1",
            alert_id,
            chat_id,
            message_id,
        )

    async def begin_delivery_attempt(
        self, conn: asyncpg.Connection, *, entitlement_id: UUID, job_id: int, attempt_no: int
    ) -> int:
        await conn.execute(
            """
            UPDATE entitlements
            SET delivery_status='queued', delivery_attempt_count=delivery_attempt_count+1,
                last_delivery_attempt_at=now(), last_delivery_error=NULL
            WHERE id=$1 AND delivery_status <> 'delivered'
            """,
            entitlement_id,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO delivery_attempts (entitlement_id, job_id, attempt_no, status)
            VALUES ($1,$2,$3,'started')
            ON CONFLICT (entitlement_id, job_id, attempt_no) DO UPDATE SET status='started'
            RETURNING id
            """,
            entitlement_id,
            job_id,
            attempt_no,
        )
        return int(row["id"])

    async def finish_delivery_attempt(
        self,
        conn: asyncpg.Connection,
        *,
        attempt_id: int,
        status: str,
        message_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await conn.execute(
            """
            UPDATE delivery_attempts
            SET status=$2, telegram_message_id=$3, error_code=$4,
                error_message=$5, finished_at=now()
            WHERE id=$1
            """,
            attempt_id,
            status,
            message_id,
            error_code,
            (error_message or "")[:4000] or None,
        )

    async def mark_delivery_failed(
        self, conn: asyncpg.Connection, *, entitlement_id: UUID, error: str
    ) -> None:
        await conn.execute(
            """
            UPDATE entitlements
            SET delivery_status='failed', last_delivery_error=$2,
                metadata=metadata || jsonb_build_object('delivery_error',$2::text)
            WHERE id=$1 AND delivery_status <> 'delivered'
            """,
            entitlement_id,
            error[:4000],
        )

    async def retryable_entitlements(
        self,
        conn: asyncpg.Connection,
        *,
        stale_minutes: int,
        max_delivery_attempts: int,
        limit: int = 100,
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT e.id, e.delivery_status, e.delivery_attempt_count
                FROM entitlements e
                WHERE e.delivery_status IN ('pending','queued','failed')
                  AND e.delivery_attempt_count < $2
                  AND (
                    e.delivery_status IN ('pending','failed') OR
                    COALESCE(e.last_delivery_attempt_at, e.granted_at) < now() - make_interval(mins => $1)
                  )
                ORDER BY COALESCE(e.last_delivery_attempt_at, e.granted_at) ASC
                FOR UPDATE SKIP LOCKED
                LIMIT $3
                """,
                stale_minutes,
                max_delivery_attempts,
                limit,
            )
        )

    async def stale_payment_ids(
        self, conn: asyncpg.Connection, *, minutes: int, limit: int = 100
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                """
                SELECT id, public_id, status, updated_at
                FROM payments
                WHERE status IN ('pending_review','flagged')
                  AND updated_at < now() - make_interval(mins => $1)
                ORDER BY updated_at ASC
                LIMIT $2
                """,
                minutes,
                limit,
            )
        )

    async def create_or_get_support_case(
        self,
        conn: asyncpg.Connection,
        *,
        public_id: str,
        user_id: UUID,
        product_id: UUID | None,
        order_id: UUID | None,
        subject: str | None = None,
    ) -> asyncpg.Record:
        existing = await conn.fetchrow(
            """
            SELECT * FROM support_cases
            WHERE user_id=$1
              AND product_id IS NOT DISTINCT FROM $2
              AND order_id IS NOT DISTINCT FROM $3
              AND subject IS NOT DISTINCT FROM $4
              AND status IN ('open','waiting_customer','waiting_admin')
            ORDER BY opened_at DESC LIMIT 1
            FOR UPDATE
            """,
            user_id,
            product_id,
            order_id,
            subject,
        )
        if existing:
            return existing
        return await conn.fetchrow(
            """
            INSERT INTO support_cases (public_id, user_id, product_id, order_id, subject, status)
            VALUES ($1,$2,$3,$4,$5,'open') RETURNING *
            """,
            public_id,
            user_id,
            product_id,
            order_id,
            subject,
        )

    async def add_support_message(
        self,
        conn: asyncpg.Connection,
        *,
        case_id: UUID,
        sender_type: str,
        body: str | None,
        sender_user_id: UUID | None = None,
        sender_admin_id: UUID | None = None,
        telegram_message_id: int | None = None,
        attachment: dict[str, Any] | None = None,
    ) -> asyncpg.Record:
        row = await conn.fetchrow(
            """
            INSERT INTO support_messages (
              case_id, sender_type, sender_user_id, sender_admin_id,
              telegram_message_id, body, attachment
            ) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) RETURNING *
            """,
            case_id,
            sender_type,
            sender_user_id,
            sender_admin_id,
            telegram_message_id,
            body,
            attachment if attachment else None,
        )
        await conn.execute(
            "UPDATE support_cases SET status=$2, updated_at=now() WHERE id=$1",
            case_id,
            "waiting_admin" if sender_type == "user" else "waiting_customer",
        )
        return row

    async def support_context(self, conn: asyncpg.Connection, *, case_public_id: str) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            SELECT sc.*, u.telegram_id, u.first_name, u.username, u.preferred_language
            FROM support_cases sc JOIN users u ON u.id=sc.user_id
            WHERE sc.public_id=$1
            """,
            case_public_id,
        )

    async def record_support_ops_message(
        self,
        conn: asyncpg.Connection,
        *,
        case_id: UUID,
        support_message_id: int | None,
        chat_id: int,
        thread_id: int | None,
        message_id: int,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO support_ops_messages (
              case_id, support_message_id, ops_chat_id, ops_thread_id, ops_message_id
            ) VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (ops_chat_id, ops_message_id) DO NOTHING
            """,
            case_id,
            support_message_id,
            chat_id,
            thread_id,
            message_id,
        )

    async def resolve_support_case(self, conn: asyncpg.Connection, *, case_public_id: str) -> asyncpg.Record | None:
        return await conn.fetchrow(
            """
            UPDATE support_cases SET status='resolved', resolved_at=now(), updated_at=now()
            WHERE public_id=$1 AND status <> 'closed'
            RETURNING *
            """,
            case_public_id,
        )
