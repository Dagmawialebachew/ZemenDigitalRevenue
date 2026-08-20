from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.control import ControlRepository
from backend.services.operations import OperationsService
from backend.services.payments import PaymentService


class ControlService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = ControlRepository()

    async def overview(self, *, days: int = 14) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            return await self.repo.overview(conn, days=days)

    async def payments(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.payments(conn, status=status, limit=limit, offset=offset)]

    async def orders(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.orders(conn, status=status, limit=limit, offset=offset)]

    async def deliveries(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.deliveries(conn, status=status, limit=limit, offset=offset)]

    async def customers(self, *, search: str | None, stage: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.customers(conn, search=search, stage=stage, limit=limit, offset=offset)]

    async def customer_detail(self, *, user_id: UUID) -> dict[str, Any] | None:
        async with self.db.acquire() as conn:
            return await self.repo.customer_detail(conn, user_id=user_id)

    async def products(self) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.products(conn)]

    async def support(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.support(conn, status=status, limit=limit, offset=offset)]

    async def support_thread(self, *, case_public_id: str) -> dict[str, Any] | None:
        async with self.db.acquire() as conn:
            return await self.repo.support_thread(conn, case_public_id=case_public_id)

    async def alerts(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.alerts(conn, status=status, limit=limit, offset=offset)]

    async def resolve_alert(self, *, alert_id: UUID, admin_telegram_id: int) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            changed = await self.repo.resolve_alert(conn, alert_id=alert_id, admin_telegram_id=admin_telegram_id)
            if changed:
                admin = await conn.fetchrow("SELECT id FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE", admin_telegram_id)
                await conn.execute(
                    """
                    INSERT INTO audit_logs(actor_type,actor_admin_id,action,entity_type,entity_id,after_data,metadata)
                    VALUES('admin',$1,'alert.resolve','operational_alert',$2,$3::jsonb,$4::jsonb)
                    """,
                    admin["id"] if admin else None,
                    str(alert_id),
                    {"status": "resolved"},
                    {"admin_telegram_id": admin_telegram_id, "surface": "control_room"},
                )
        return {"changed": changed, "status": "resolved" if changed else "unchanged"}

    async def approve_payment(self, *, payment_public_id: str, proof_id: UUID | None, admin_telegram_id: int) -> dict[str, Any]:
        result = await PaymentService(self.db, self.settings).approve(
            payment_public_id=payment_public_id,
            admin_telegram_id=admin_telegram_id,
            expected_proof_id=proof_id,
        )
        return result.__dict__ if hasattr(result, "__dict__") else {
            "changed": result.changed,
            "payment_public_id": result.payment_public_id,
            "order_public_id": result.order_public_id,
            "product_title": result.product_title,
            "buyer_telegram_id": result.buyer_telegram_id,
            "buyer_name": result.buyer_name,
            "language": result.language,
            "status": result.status,
            "amount_br": result.amount_br,
        }

    async def reject_payment(self, *, payment_public_id: str, proof_id: UUID | None, admin_telegram_id: int, reason: str, reason_text: str | None) -> dict[str, Any]:
        result = await PaymentService(self.db, self.settings).reject(
            payment_public_id=payment_public_id,
            admin_telegram_id=admin_telegram_id,
            reason_value=reason,
            reason_text=reason_text,
            expected_proof_id=proof_id,
        )
        return {
            "changed": result.changed,
            "payment_public_id": result.payment_public_id,
            "order_public_id": result.order_public_id,
            "status": result.status,
            "amount_br": result.amount_br,
        }

    async def flag_payment(self, *, payment_public_id: str, proof_id: UUID | None, admin_telegram_id: int) -> dict[str, Any]:
        result = await PaymentService(self.db, self.settings).flag(
            payment_public_id=payment_public_id,
            admin_telegram_id=admin_telegram_id,
            expected_proof_id=proof_id,
        )
        return {"changed": result.changed, "payment_public_id": result.payment_public_id, "status": result.status}

    async def retry_delivery(self, *, entitlement_id: UUID, admin_telegram_id: int) -> dict[str, object]:
        return await OperationsService(self.db, self.settings).retry_delivery(
            entitlement_id=entitlement_id, actor=f"control:{admin_telegram_id}"
        )

    async def reply_support(self, *, case_public_id: str, admin_telegram_id: int, text: str) -> dict[str, Any]:
        return await OperationsService(self.db, self.settings).admin_reply_support(
            case_public_id=case_public_id, admin_telegram_id=admin_telegram_id, text=text
        )

    async def resolve_support(self, *, case_public_id: str, admin_telegram_id: int) -> dict[str, Any]:
        return await OperationsService(self.db, self.settings).resolve_support(
            case_public_id=case_public_id, admin_telegram_id=admin_telegram_id
        )
