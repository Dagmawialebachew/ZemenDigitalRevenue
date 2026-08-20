from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.finalization import (
    cash_view,
    normalize_dashboard_setting,
    normalize_admin_role,
    normalize_expense_category,
)
from backend.repositories.final_control import FinalControlRepository


_ROLE_LEVEL = {"viewer": 0, "operator": 1, "admin": 2, "owner": 3}


class FinalControlService:
    def __init__(self, db: Database, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.repo = FinalControlRepository()

    async def _admin(self, conn: Any, telegram_id: int) -> dict[str, Any]:
        row = await conn.fetchrow(
            "SELECT id,telegram_id,display_name,role,is_active FROM admin_users WHERE telegram_id=$1 AND is_active=TRUE",
            telegram_id,
        )
        if row:
            return dict(row)
        if telegram_id in self.settings.admin_telegram_ids:
            return {"id": None, "telegram_id": telegram_id, "display_name": "Zemen Admin", "role": "owner", "is_active": True}
        raise PermissionError("admin access revoked")

    @staticmethod
    def _require_role(admin: dict[str, Any], minimum: str) -> None:
        if _ROLE_LEVEL.get(str(admin.get("role")), -1) < _ROLE_LEVEL[minimum]:
            raise PermissionError(f"{minimum} role required")

    async def analytics(self, *, days: int) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            data = await self.repo.analytics(conn, days=days)
        summary = data.get("summary", {})
        started = int(summary.get("started_users") or 0)
        buyers = int(summary.get("buyers") or 0)
        summary["start_to_buyer_percent"] = round((buyers / started * 100), 2) if started else 0.0
        return data

    async def financials(self, *, days: int) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            data = await self.repo.financials(conn, days=days)
        summary = data.get("summary", {})
        cash = cash_view(
            gross_revenue_br=summary.get("gross_revenue_br") or 0,
            refunds_br=summary.get("refunds_br") or 0,
            recorded_expenses_br=summary.get("recorded_expenses_br") or 0,
            paid_commissions_br=summary.get("paid_commissions_br") or 0,
        )
        summary["net_cash_br"] = cash.net_cash_br
        summary["net_cash_definition"] = "gross revenue - refunds - recorded expenses - paid referral commissions"
        return data

    async def create_expense(
        self,
        *,
        admin_telegram_id: int,
        expense_date: date,
        category: str,
        amount_br: Decimal,
        description: str,
        reference: str | None,
    ) -> dict[str, Any]:
        category = normalize_expense_category(category)
        if amount_br <= 0:
            raise ValueError("amount must be positive")
        description = description.strip()
        if not description:
            raise ValueError("description is required")
        async with self.db.transaction() as conn:
            admin = await self._admin(conn, admin_telegram_id)
            self._require_role(admin, "admin")
            row = await self.repo.create_expense(
                conn,
                expense_date=expense_date,
                category=category,
                amount_br=amount_br,
                description=description,
                reference=reference.strip() if reference else None,
                admin_id=admin["id"],
            )
            await self._audit(
                conn,
                admin=admin,
                action="finance.expense.create",
                entity_type="business_expense",
                entity_id=str(row["id"]),
                after=dict(row),
            )
        return dict(row)

    async def delete_expense(self, *, admin_telegram_id: int, expense_id: UUID) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            admin = await self._admin(conn, admin_telegram_id)
            self._require_role(admin, "admin")
            row = await self.repo.delete_expense(conn, expense_id=expense_id)
            if row is None:
                raise LookupError("expense not found")
            await self._audit(
                conn,
                admin=admin,
                action="finance.expense.delete",
                entity_type="business_expense",
                entity_id=str(expense_id),
                before=dict(row),
            )
        return {"deleted": True, "id": str(expense_id)}

    async def reviews(self, *, status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        async with self.db.acquire() as conn:
            return [dict(r) for r in await self.repo.reviews(conn, status=status, limit=limit, offset=offset)]

    async def moderate_review(
        self,
        *,
        admin_telegram_id: int,
        review_id: UUID,
        status: str,
        featured: bool,
    ) -> dict[str, Any]:
        if status not in {"approved", "rejected", "pending"}:
            raise ValueError("invalid review status")
        async with self.db.transaction() as conn:
            admin = await self._admin(conn, admin_telegram_id)
            self._require_role(admin, "operator")
            before = await conn.fetchrow("SELECT * FROM reviews WHERE id=$1", review_id)
            if before is None:
                raise LookupError("review not found")
            row = await self.repo.moderate_review(
                conn,
                review_id=review_id,
                new_status=status,
                featured=featured,
                admin_id=admin["id"],
            )
            await self._audit(
                conn,
                admin=admin,
                action="review.moderate",
                entity_type="review",
                entity_id=str(review_id),
                before=dict(before),
                after=dict(row) if row else None,
            )
        return dict(row) if row else {}

    async def settings_bundle(self, *, admin_telegram_id: int) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            admin = await self._admin(conn, admin_telegram_id)
            settings = [dict(r) for r in await self.repo.settings(conn)]
            admins = [dict(r) for r in await self.repo.admins(conn)] if admin["role"] == "owner" else []
            audit = [dict(r) for r in await self.repo.audit(conn, limit=100)] if _ROLE_LEVEL[admin["role"]] >= _ROLE_LEVEL["admin"] else []
        return {"settings": settings, "admins": admins, "audit": audit, "role": admin["role"]}

    async def set_setting(self, *, admin_telegram_id: int, key: str, value: Any) -> dict[str, Any]:
        key = key.strip().lower()
        value = normalize_dashboard_setting(key, value)
        async with self.db.transaction() as conn:
            admin = await self._admin(conn, admin_telegram_id)
            self._require_role(admin, "admin")
            before = await conn.fetchrow("SELECT * FROM settings WHERE key=$1", key)
            row = await self.repo.set_setting(
                conn,
                key=key,
                value=json.dumps(value, ensure_ascii=False),
                admin_id=admin["id"],
            )
            await self._audit(
                conn,
                admin=admin,
                action="setting.update",
                entity_type="setting",
                entity_id=key,
                before=dict(before) if before else None,
                after=dict(row),
            )
        return dict(row)

    async def upsert_admin(
        self,
        *,
        actor_telegram_id: int,
        telegram_id: int,
        display_name: str,
        role: str,
    ) -> dict[str, Any]:
        role = normalize_admin_role(role)
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("display name is required")
        async with self.db.transaction() as conn:
            actor = await self._admin(conn, actor_telegram_id)
            self._require_role(actor, "owner")
            before = await conn.fetchrow("SELECT * FROM admin_users WHERE telegram_id=$1", telegram_id)
            row = await self.repo.upsert_admin(conn, telegram_id=telegram_id, display_name=display_name, role=role)
            await self._audit(
                conn,
                admin=actor,
                action="admin.upsert",
                entity_type="admin_user",
                entity_id=str(row["id"]),
                before=dict(before) if before else None,
                after=dict(row),
            )
        return dict(row)

    async def set_admin_active(
        self,
        *,
        actor_telegram_id: int,
        admin_id: UUID,
        active: bool,
    ) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            actor = await self._admin(conn, actor_telegram_id)
            self._require_role(actor, "owner")
            before = await conn.fetchrow("SELECT * FROM admin_users WHERE id=$1", admin_id)
            if before is None:
                raise LookupError("admin not found")
            if int(before["telegram_id"] or 0) == actor_telegram_id and not active:
                raise ValueError("you cannot disable your own active admin record")
            row = await self.repo.set_admin_active(conn, admin_id=admin_id, active=active)
            await self._audit(
                conn,
                admin=actor,
                action="admin.active.set",
                entity_type="admin_user",
                entity_id=str(admin_id),
                before=dict(before),
                after=dict(row) if row else None,
            )
        return dict(row) if row else {}

    async def _audit(
        self,
        conn: Any,
        *,
        admin: dict[str, Any],
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO audit_logs(actor_type,actor_admin_id,action,entity_type,entity_id,before_data,after_data,metadata)
            VALUES('admin',$1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb)
            """,
            admin.get("id"),
            action,
            entity_type,
            entity_id,
            json.dumps(before, default=str) if before is not None else None,
            json.dumps(after, default=str) if after is not None else None,
            json.dumps({"admin_telegram_id": admin["telegram_id"], "surface": "zemen_control"}),
        )
