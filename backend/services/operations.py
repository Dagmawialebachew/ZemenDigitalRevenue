from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any
from uuid import UUID, uuid4

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.events import EventRepository
from backend.repositories.jobs import JobRepository
from backend.repositories.operations import OperationsRepository
from workers.models import EnqueueJob


class OperationsService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = OperationsRepository()
        self.jobs = JobRepository(db)
        self.events = EventRepository()

    async def overview(self) -> dict[str, int]:
        async with self.db.acquire() as conn:
            return await self.repo.overview(conn)

    async def queues(self, *, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
        limit = max(1, min(limit, 250))
        async with self.db.acquire() as conn:
            payments = [dict(r) for r in await self.repo.payment_queue(conn, limit=limit)]
            deliveries = [dict(r) for r in await self.repo.delivery_queue(conn, limit=limit)]
            support = [dict(r) for r in await self.repo.support_queue(conn, limit=limit)]
            alerts = [dict(r) for r in await self.repo.alerts(conn, limit=limit)]
        return {"payments": payments, "deliveries": deliveries, "support": support, "alerts": alerts}

    async def retry_delivery(self, *, entitlement_id: UUID, actor: str = "ops_api") -> dict[str, object]:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                "SELECT id, delivery_status FROM entitlements WHERE id=$1 FOR UPDATE", entitlement_id
            )
            if row is None:
                raise LookupError("entitlement not found")
            if row["delivery_status"] == "delivered":
                return {"queued": False, "reason": "already delivered"}
            await conn.execute(
                "UPDATE entitlements SET delivery_status='queued', last_delivery_error=NULL WHERE id=$1",
                entitlement_id,
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.delivery.product",
                    queue="delivery",
                    job_key=f"delivery:manual:{entitlement_id}:{uuid4().hex[:10]}",
                    payload={"entitlement_id": str(entitlement_id), "recovery": True, "actor": actor},
                    max_attempts=self.settings.delivery_job_max_attempts,
                    priority=20,
                ),
            )
        return {"queued": True, "entitlement_id": str(entitlement_id)}

    async def recover_deliveries(self, *, limit: int = 100) -> dict[str, int]:
        scanned = requeued = skipped = 0
        async with self.db.transaction() as conn:
            rows = await self.repo.retryable_entitlements(
                conn,
                stale_minutes=self.settings.delivery_stale_minutes,
                max_delivery_attempts=self.settings.delivery_max_total_attempts,
                limit=limit,
            )
            scanned = len(rows)
            bucket = datetime.now(UTC).strftime("%Y%m%d%H%M")
            for row in rows:
                if row["delivery_status"] == "delivered":
                    skipped += 1
                    continue
                await conn.execute(
                    "UPDATE entitlements SET delivery_status='queued', last_delivery_error=NULL WHERE id=$1",
                    row["id"],
                )
                await self.jobs.enqueue_in_tx(
                    conn,
                    EnqueueJob(
                        job_type="telegram.delivery.product",
                        queue="delivery",
                        job_key=f"delivery:recovery:{row['id']}:{bucket}",
                        payload={"entitlement_id": str(row["id"]), "recovery": True},
                        max_attempts=self.settings.delivery_job_max_attempts,
                        priority=30,
                    ),
                )
                requeued += 1
        return {"scanned": scanned, "requeued": requeued, "skipped": skipped}

    async def maintenance_tick(self, *, current_job_id: int | None = None, schedule_next: bool = True) -> dict[str, int]:
        recovered = await self.recover_deliveries(limit=self.settings.ops_maintenance_batch_size)
        stale_alerts = 0
        async with self.db.transaction() as conn:
            stale = await self.repo.stale_payment_ids(
                conn,
                minutes=self.settings.payment_review_stale_minutes,
                limit=self.settings.ops_maintenance_batch_size,
            )
            for payment in stale:
                alert = await self.repo.upsert_alert(
                    conn,
                    alert_key=f"stale-payment:{payment['id']}",
                    severity="warning",
                    alert_type="payment_review_stale",
                    title=f"Payment waiting too long · {payment['public_id']}",
                    body=f"Status {payment['status']} since {payment['updated_at'].isoformat()}",
                    entity_type="payment",
                    entity_id=str(payment["id"]),
                    metadata={"payment_public_id": payment["public_id"]},
                )
                await self.jobs.enqueue_in_tx(
                    conn,
                    EnqueueJob(
                        job_type="telegram.ops.alert",
                        queue="telegram",
                        job_key=f"ops-alert:{alert['id']}",
                        payload={"alert_id": str(alert["id"])},
                        priority=15,
                    ),
                )
                stale_alerts += 1

            if schedule_next:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM jobs
                    WHERE job_type='operations.maintenance'
                      AND status IN ('queued','running')
                      AND ($1::bigint IS NULL OR id <> $1)
                    ORDER BY run_at ASC LIMIT 1
                    """,
                    current_job_id,
                )
                if existing is None:
                    next_run = datetime.now(UTC) + timedelta(seconds=self.settings.ops_maintenance_interval_seconds)
                    next_bucket = next_run.strftime("%Y%m%d%H%M%S")
                    await self.jobs.enqueue_in_tx(
                        conn,
                        EnqueueJob(
                            job_type="operations.maintenance",
                            queue="default",
                            job_key=f"operations:maintenance:{next_bucket}",
                            payload={},
                            run_at=next_run,
                            max_attempts=3,
                            priority=200,
                        ),
                    )
        return {**recovered, "stale_payment_alerts": stale_alerts}

    async def ensure_maintenance_job(self) -> None:
        async with self.db.transaction() as conn:
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", "zemen:ops:maintenance")
            existing = await conn.fetchval(
                "SELECT id FROM jobs WHERE job_type='operations.maintenance' AND status IN ('queued','running') LIMIT 1"
            )
            if existing is not None:
                return
            run_at = datetime.now(UTC) + timedelta(seconds=5)
            bucket = run_at.strftime("%Y%m%d%H%M%S")
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="operations.maintenance",
                    queue="default",
                    job_key=f"operations:maintenance:{bucket}",
                    payload={},
                    run_at=run_at,
                    max_attempts=3,
                    priority=200,
                ),
            )

    async def open_support(
        self,
        *,
        user_id: UUID,
        product_id: UUID | None = None,
        order_id: UUID | None = None,
        subject: str | None = None,
    ) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            case = await self.repo.create_or_get_support_case(
                conn,
                public_id=f"ZD-SUP-{uuid4().hex[:8].upper()}",
                user_id=user_id,
                product_id=product_id,
                order_id=order_id,
                subject=subject,
            )
            await conn.execute(
                """
                UPDATE conversation_sessions SET active_flow='support', step_key='awaiting_support_message',
                    last_interaction_at=now(), updated_at=now() WHERE user_id=$1
                """,
                user_id,
            )
            await self.events.append(
                conn,
                event_type="SUPPORT_OPENED",
                user_id=user_id,
                product_id=product_id,
                order_id=order_id,
                payload={"case_public_id": case["public_id"], "subject": subject},
            )
        return dict(case)

    async def submit_support_message(
        self,
        *,
        user_id: UUID,
        telegram_message_id: int,
        body: str | None,
        attachment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            session = await conn.fetchrow(
                "SELECT * FROM conversation_sessions WHERE user_id=$1 FOR UPDATE", user_id
            )
            if session is None or session["active_flow"] != "support":
                raise LookupError("support session not active")
            case = await conn.fetchrow(
                """
                SELECT * FROM support_cases
                WHERE user_id=$1 AND status IN ('open','waiting_customer','waiting_admin')
                ORDER BY opened_at DESC LIMIT 1 FOR UPDATE
                """,
                user_id,
            )
            if case is None:
                raise LookupError("support case not found")
            msg = await self.repo.add_support_message(
                conn,
                case_id=case["id"],
                sender_type="user",
                sender_user_id=user_id,
                body=body,
                telegram_message_id=telegram_message_id,
                attachment=attachment,
            )
            await conn.execute(
                "UPDATE conversation_sessions SET step_key='support_waiting_admin', updated_at=now() WHERE user_id=$1",
                user_id,
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.ops.support_case",
                    queue="telegram",
                    job_key=f"support-ops:{msg['id']}",
                    payload={"case_public_id": case["public_id"], "support_message_id": int(msg["id"])},
                    priority=30,
                ),
            )
            await self.events.append(
                conn,
                event_type="SUPPORT_MESSAGE_SENT",
                user_id=user_id,
                product_id=case["product_id"],
                order_id=case["order_id"],
                payload={"case_public_id": case["public_id"]},
            )
        return {"case_public_id": case["public_id"], "message_id": int(msg["id"])}

    async def admin_reply_support(self, *, case_public_id: str, admin_telegram_id: int, text: str) -> dict[str, Any]:
        if admin_telegram_id not in self.settings.admin_telegram_ids:
            raise PermissionError("not authorized")
        text = text.strip()
        if not text:
            raise ValueError("reply cannot be empty")
        async with self.db.transaction() as conn:
            case = await self.repo.support_context(conn, case_public_id=case_public_id)
            if case is None:
                raise LookupError("support case not found")
            admin = await conn.fetchrow(
                "SELECT * FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE", admin_telegram_id
            )
            msg = await self.repo.add_support_message(
                conn,
                case_id=case["id"],
                sender_type="admin",
                sender_admin_id=admin["id"] if admin else None,
                body=text,
            )
            prefix = "💬 <b>Zemen Support</b>\n\n"
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.user.notify",
                    queue="telegram",
                    job_key=f"support-reply:{msg['id']}",
                    payload={"telegram_id": int(case["telegram_id"]), "text": prefix + escape(text)},
                    priority=20,
                ),
            )
        return {"case_public_id": case_public_id, "sent": True}

    async def resolve_support(self, *, case_public_id: str, admin_telegram_id: int) -> dict[str, Any]:
        if admin_telegram_id not in self.settings.admin_telegram_ids:
            raise PermissionError("not authorized")
        async with self.db.transaction() as conn:
            context = await self.repo.support_context(conn, case_public_id=case_public_id)
            if context is None:
                raise LookupError("support case not found")
            case = await self.repo.resolve_support_case(conn, case_public_id=case_public_id)
            if case is None:
                raise LookupError("support case not found")
            await conn.execute(
                """
                UPDATE conversation_sessions
                SET active_flow='home',
                    step_key='home',
                    last_interaction_at=now(),
                    updated_at=now()
                WHERE user_id=$1
                """,
                case["user_id"],
            )
            await conn.execute(
                "DELETE FROM support_reply_contexts WHERE case_id=$1",
                case["id"],
            )
            resolved_text = (
                "✅ <b>Zemen Support</b>\n\nYour support case has been marked resolved. If you still need help, tap Help again."
                if context["preferred_language"] == "en"
                else "✅ <b>Zemen Support</b>\n\nSupport caseዎ ተፈትቷል። አሁንም እገዛ ካስፈለገዎት Help እንደገና ይጫኑ።"
            )
            await self.jobs.enqueue_in_tx(
                conn,
                EnqueueJob(
                    job_type="telegram.user.notify",
                    queue="telegram",
                    job_key=f"support-resolved:{case['id']}",
                    payload={"telegram_id": int(context["telegram_id"]), "text": resolved_text},
                    priority=40,
                ),
            )
            await self.events.append(
                conn,
                event_type="SUPPORT_RESOLVED",
                user_id=case["user_id"],
                product_id=case["product_id"],
                order_id=case["order_id"],
                payload={"case_public_id": case_public_id, "admin_telegram_id": admin_telegram_id},
            )
        return {"case_public_id": case_public_id, "status": "resolved"}
