from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from aiogram.types import BufferedInputFile
from fastapi.encoders import jsonable_encoder

from backend.core.config import Settings
from backend.db.pool import Database
from backend.domain.marketing import (
    clean_automation_steps,
    clean_broadcast_content,
    get_recovery_campaign_templates,
    normalize_audience,
)
from backend.repositories.events import EventRepository
from backend.repositories.jobs import JobRepository
from backend.repositories.marketing import MarketingRepository
from workers.models import EnqueueJob


class MarketingService:
    def __init__(self, db: Database, settings: Settings, bot: Any | None = None) -> None:
        self.db = db
        self.settings = settings
        self.bot = bot
        self.repo = MarketingRepository()
        self.jobs = JobRepository(db)
        self.events = EventRepository()

    async def dashboard(self) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            return {
                "overview": await self.repo.overview(conn),
                "products": [dict(r) for r in await self.repo.product_choices(conn)],
                "broadcasts": [dict(r) for r in await self.repo.list_broadcasts(conn)],
                "automations": [dict(r) for r in await self.repo.list_automations(conn)],
                "discount_rules": [dict(r) for r in await self.repo.list_discount_rules(conn)],
                "offers": [dict(r) for r in await self.repo.list_offers(conn)],
                "links": [dict(r) | {"bot_url": self._bot_start_url(str(r["token"]))} for r in await self.repo.list_links(conn)],
                "referrals": {
                    "summary": await self.repo.referral_summary(conn),
                    "partners": [dict(r) for r in await self.repo.referral_partners(conn)],
                    "payouts": [dict(r) for r in await self.repo.payouts(conn)],
                },
            }

    async def audience_count(self, definition: dict[str, Any]) -> int:
        audience = normalize_audience(definition)
        async with self.db.acquire() as conn:
            return await self.repo.audience_count(conn, audience)

    async def create_broadcast(self, *, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()[:180]
        if not name:
            raise ValueError("Broadcast name is required")
        audience = normalize_audience(data.get("audience_definition"))
        content_am = clean_broadcast_content(data.get("content_am"))
        content_en = clean_broadcast_content(data.get("content_en"))
        if content_am is None and content_en is None:
            raise ValueError("Broadcast needs Amharic or English content")
        window = int(data.get("attribution_window_hours") or 168)
        if not 1 <= window <= 2160:
            raise ValueError("Attribution window must be between 1 and 2160 hours")
        async with self.db.transaction() as conn:
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            row = await conn.fetchrow(
                """
                INSERT INTO broadcasts(name,audience_definition,content_am,content_en,attribution_window_hours,created_by_admin_id)
                VALUES($1,$2::jsonb,$3::jsonb,$4::jsonb,$5,$6) RETURNING *
                """,
                name, audience.as_dict(), content_am, content_en, window, admin_id,
            )
            await self.repo.audit(conn, admin_id=admin_id, action="broadcast.create", entity_type="broadcast", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def update_broadcast(self, *, broadcast_id: UUID, admin_telegram_id: int, expected_revision: int, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()[:180]
        if not name:
            raise ValueError("Broadcast name is required")
        audience = normalize_audience(data.get("audience_definition"))
        content_am = clean_broadcast_content(data.get("content_am"))
        content_en = clean_broadcast_content(data.get("content_en"))
        if content_am is None and content_en is None:
            raise ValueError("Broadcast needs Amharic or English content")
        window = int(data.get("attribution_window_hours") or 168)
        if not 1 <= window <= 2160:
            raise ValueError("Attribution window must be between 1 and 2160 hours")
        async with self.db.transaction() as conn:
            before = await self.repo.broadcast(conn, broadcast_id, for_update=True)
            if before is None:
                raise LookupError("Broadcast not found")
            if before["status"] in {"sending", "sent"}:
                raise ValueError("A sending or sent broadcast is immutable")
            if int(before["revision"]) != int(expected_revision):
                raise ValueError("Broadcast changed in another session. Refresh before saving.")
            row = await conn.fetchrow(
                """
                UPDATE broadcasts SET name=$2,audience_definition=$3::jsonb,content_am=$4::jsonb,content_en=$5::jsonb,
                    attribution_window_hours=$6,revision=revision+1,
                    status=CASE WHEN status='scheduled' THEN 'draft' ELSE status END,
                    scheduled_at=CASE WHEN status='scheduled' THEN NULL ELSE scheduled_at END,
                    updated_at=now()
                WHERE id=$1 RETURNING *
                """,
                broadcast_id, name, audience.as_dict(), content_am, content_en, window,
            )
            if before["status"] == "scheduled":
                # The old dispatch job is made stale by the revision bump. Clear
                # its snapshot so the edited recipe must be deliberately sent again.
                await conn.execute("DELETE FROM broadcast_recipients WHERE broadcast_id=$1", broadcast_id)
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="broadcast.update", entity_type="broadcast", entity_id=str(broadcast_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def schedule_broadcast(self, *, broadcast_id: UUID, admin_telegram_id: int, scheduled_at: datetime | None) -> dict[str, Any]:
        when = scheduled_at or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        async with self.db.transaction() as conn:
            row = await self.repo.broadcast(conn, broadcast_id, for_update=True)
            if row is None:
                raise LookupError("Broadcast not found")
            if row["status"] in {"sending", "sent", "cancelled"}:
                raise ValueError(f"Broadcast cannot be scheduled from {row['status']}")
            audience = normalize_audience(dict(row["audience_definition"] or {}))
            await conn.execute("DELETE FROM broadcast_recipients WHERE broadcast_id=$1", broadcast_id)
            audience_size = await self.repo.snapshot_broadcast_audience(conn, broadcast_id=broadcast_id, audience=audience)
            if audience_size == 0:
                raise ValueError("Audience currently contains 0 reachable users")
            new_revision = int(row["revision"]) + 1
            updated = await conn.fetchrow(
                """
                UPDATE broadcasts SET status='scheduled',scheduled_at=$2,audience_snapshot_count=$3,
                    revision=$4,cancel_requested_at=NULL,started_at=NULL,completed_at=NULL,updated_at=now()
                WHERE id=$1 RETURNING *
                """,
                broadcast_id, when, audience_size, new_revision,
            )
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            job = await self.jobs.enqueue_in_tx(conn, EnqueueJob(
                job_type="marketing.broadcast.dispatch", queue="broadcast",
                job_key=f"broadcast:dispatch:{broadcast_id}:r{new_revision}:batch:1",
                payload={"broadcast_id": str(broadcast_id), "batch_no": 1, "revision": new_revision},
                run_at=when, priority=60, max_attempts=8,
            ))
            await self.repo.audit(conn, admin_id=admin_id, action="broadcast.schedule", entity_type="broadcast", entity_id=str(broadcast_id), after={"scheduled_at": when.isoformat(), "audience_snapshot_count": audience_size, "job_id": job.id})
        return dict(updated)

    async def cancel_broadcast(self, *, broadcast_id: UUID, admin_telegram_id: int) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            before = await self.repo.broadcast(conn, broadcast_id, for_update=True)
            if before is None:
                raise LookupError("Broadcast not found")
            if before["status"] == "sent":
                raise ValueError("A completed broadcast cannot be cancelled")
            row = await conn.fetchrow(
                """
                UPDATE broadcasts SET status='cancelled',cancel_requested_at=now(),updated_at=now() WHERE id=$1 RETURNING *
                """, broadcast_id,
            )
            await conn.execute(
                "UPDATE broadcast_recipients SET status='skipped',updated_at=now() WHERE broadcast_id=$1 AND status='queued'",
                broadcast_id,
            )
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="broadcast.cancel", entity_type="broadcast", entity_id=str(broadcast_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def upload_broadcast_media(self, *, filename: str, content_type: str | None, data: bytes) -> dict[str, str]:
        if not self.bot or not self.settings.telegram_storage_chat_id:
            raise RuntimeError("TELEGRAM_STORAGE_CHAT_ID and a connected bot are required for broadcast uploads")
        max_bytes = self.settings.marketing_upload_max_mb * 1024 * 1024
        if not data or len(data) > max_bytes:
            raise ValueError(f"File must be between 1 byte and {self.settings.marketing_upload_max_mb} MB")
        mime = (content_type or "application/octet-stream").lower()
        upload = BufferedInputFile(data, filename=filename)
        if mime.startswith("image/"):
            msg = await self.bot.send_photo(chat_id=self.settings.telegram_storage_chat_id, photo=upload, caption="Zemen broadcast media")
            if not msg.photo:
                raise RuntimeError("Telegram did not return a photo file_id")
            return {"type": "photo", "file_id": msg.photo[-1].file_id, "file_unique_id": msg.photo[-1].file_unique_id}
        if mime.startswith("video/"):
            msg = await self.bot.send_video(chat_id=self.settings.telegram_storage_chat_id, video=upload, caption="Zemen broadcast media")
            if not msg.video:
                raise RuntimeError("Telegram did not return a video file_id")
            return {"type": "video", "file_id": msg.video.file_id, "file_unique_id": msg.video.file_unique_id}
        msg = await self.bot.send_document(chat_id=self.settings.telegram_storage_chat_id, document=upload, caption="Zemen broadcast media")
        if not msg.document:
            raise RuntimeError("Telegram did not return a document file_id")
        return {"type": "document", "file_id": msg.document.file_id, "file_unique_id": msg.document.file_unique_id}

    async def create_automation(self, *, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()[:180]
        trigger = str(data.get("trigger_event") or "").strip().upper()[:100]
        if not name or not trigger:
            raise ValueError("Automation name and trigger event are required")
        audience = normalize_audience(data.get("audience_definition"))
        steps = clean_automation_steps(list(data.get("steps") or []))
        product_id = UUID(str(data["product_id"])) if data.get("product_id") else None
        trigger_config = dict(data.get("trigger_config") or {})
        trigger_config.setdefault("stop_on_purchase", True)
        trigger_config.setdefault("stop_on_pending_payment", True)
        async with self.db.transaction() as conn:
            if product_id and not await conn.fetchval("SELECT 1 FROM products WHERE id=$1", product_id):
                raise LookupError("Product not found")
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            row = await conn.fetchrow(
                """
                INSERT INTO automations(name,description,product_id,trigger_event,is_enabled,stop_conditions,audience_definition,trigger_config,priority,created_by_admin_id)
                VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9,$10) RETURNING *
                """,
                name, data.get("description"), product_id, trigger, bool(data.get("is_enabled", False)),
                list(data.get("stop_conditions") or []), audience.as_dict(), trigger_config,
                int(data.get("priority") or 100), admin_id,
            )
            for step in steps:
                await conn.execute(
                    """INSERT INTO automation_steps(automation_id,step_key,sort_order,step_type,config) VALUES($1,$2,$3,$4,$5::jsonb)""",
                    row["id"], step["step_key"], step["sort_order"], step["step_type"], step["config"],
                )
            await self.repo.audit(conn, admin_id=admin_id, action="automation.create", entity_type="automation", entity_id=str(row["id"]), after={"automation": jsonable_encoder(dict(row)), "steps": steps})
        return await self.automation_detail(row["id"])

    async def update_automation(self, *, automation_id: UUID, admin_telegram_id: int, expected_revision: int, data: dict[str, Any]) -> dict[str, Any]:
        name = str(data.get("name") or "").strip()[:180]
        trigger = str(data.get("trigger_event") or "").strip().upper()[:100]
        if not name or not trigger:
            raise ValueError("Automation name and trigger event are required")
        audience = normalize_audience(data.get("audience_definition"))
        steps = clean_automation_steps(list(data.get("steps") or []))
        product_id = UUID(str(data["product_id"])) if data.get("product_id") else None
        trigger_config = dict(data.get("trigger_config") or {})
        trigger_config.setdefault("stop_on_purchase", True)
        trigger_config.setdefault("stop_on_pending_payment", True)
        async with self.db.transaction() as conn:
            before = await self.repo.automation(conn, automation_id, for_update=True)
            if before is None:
                raise LookupError("Automation not found")
            if int(before["revision"]) != int(expected_revision):
                raise ValueError("Automation changed in another session. Refresh before saving.")
            if product_id and not await conn.fetchval("SELECT 1 FROM products WHERE id=$1", product_id):
                raise LookupError("Product not found")
            row = await conn.fetchrow(
                """
                UPDATE automations SET name=$2,description=$3,product_id=$4,trigger_event=$5,is_enabled=$6,
                    stop_conditions=$7::jsonb,audience_definition=$8::jsonb,trigger_config=$9::jsonb,priority=$10,
                    version=version+1,revision=revision+1,updated_at=now() WHERE id=$1 RETURNING *
                """,
                automation_id, name, data.get("description"), product_id, trigger, bool(data.get("is_enabled", False)),
                list(data.get("stop_conditions") or []), audience.as_dict(), trigger_config, int(data.get("priority") or 100),
            )
            # Editing a live recipe never mutates an in-flight customer journey.
            await conn.execute(
                """UPDATE automation_runs SET status='stopped',stop_reason='automation_edited',completed_at=now(),updated_at=now()
                   WHERE automation_id=$1 AND status IN ('active','waiting')""",
                automation_id,
            )
            await conn.execute("DELETE FROM automation_steps WHERE automation_id=$1", automation_id)
            for step in steps:
                await conn.execute(
                    "INSERT INTO automation_steps(automation_id,step_key,sort_order,step_type,config) VALUES($1,$2,$3,$4,$5::jsonb)",
                    automation_id, step["step_key"], step["sort_order"], step["step_type"], step["config"],
                )
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="automation.update", entity_type="automation", entity_id=str(automation_id), before=jsonable_encoder(dict(before)), after={"automation": jsonable_encoder(dict(row)), "steps": steps})
        return await self.automation_detail(automation_id)

    async def automation_detail(self, automation_id: UUID) -> dict[str, Any]:
        async with self.db.acquire() as conn:
            row = await self.repo.automation(conn, automation_id)
            if row is None:
                raise LookupError("Automation not found")
            steps = await self.repo.automation_steps(conn, automation_id)
        return {"automation": dict(row), "steps": [dict(s) for s in steps]}

    async def set_automation_enabled(self, *, automation_id: UUID, admin_telegram_id: int, enabled: bool) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            before = await self.repo.automation(conn, automation_id, for_update=True)
            if before is None:
                raise LookupError("Automation not found")
            if enabled and not await conn.fetchval("SELECT 1 FROM automation_steps WHERE automation_id=$1", automation_id):
                raise ValueError("Automation needs at least one step")
            row = await conn.fetchrow("UPDATE automations SET is_enabled=$2,revision=revision+1,updated_at=now() WHERE id=$1 RETURNING *", automation_id, enabled)
            if not enabled:
                await conn.execute("UPDATE automation_runs SET status='stopped',stop_reason='automation_disabled',completed_at=now(),updated_at=now() WHERE automation_id=$1 AND status IN ('active','waiting')", automation_id)
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="automation.enable" if enabled else "automation.disable", entity_type="automation", entity_id=str(automation_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def create_discount_rule(self, *, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        product_id = UUID(str(data["product_id"]))
        name = str(data.get("name") or "Recovery offer").strip()[:180]
        target = Decimal(str(data.get("target_price_br")))
        delay = int(data.get("eligibility_delay_seconds") or 0)
        expires = int(data.get("expires_after_seconds") or 0) or None
        score = int(data.get("minimum_intent_score") or 0)
        rule_type = str(data.get("rule_type") or "recovery").strip().lower()
        if rule_type not in {"recovery", "manual", "campaign"}:
            raise ValueError("Unsupported discount rule type")
        if not 0 <= score <= 1000:
            raise ValueError("minimum_intent_score must be between 0 and 1000")
        async with self.db.transaction() as conn:
            product = await conn.fetchrow("SELECT * FROM products WHERE id=$1 FOR UPDATE", product_id)
            if product is None:
                raise LookupError("Product not found")
            regular = Decimal(str(product["regular_price_br"]))
            if target <= 0 or target >= regular:
                raise ValueError("Recovery price must be positive and below regular price")
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            row = await conn.fetchrow(
                """
                INSERT INTO discount_rules(product_id,name,rule_type,target_price_br,eligibility_delay_seconds,expires_after_seconds,is_active,created_by_admin_id,require_no_pending_payment,minimum_intent_score,metadata)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb) RETURNING *
                """,
                product_id, name, rule_type, target, delay, expires,
                bool(data.get("is_active", True)), admin_id, bool(data.get("require_no_pending_payment", True)), score,
                {"commissionable": False, "source": "zemen_control"},
            )
            await self.repo.audit(conn, admin_id=admin_id, action="discount_rule.create", entity_type="discount_rule", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def update_discount_rule(
        self,
        *,
        rule_id: UUID,
        admin_telegram_id: int,
        expected_revision: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(data.get("name") or "Recovery offer").strip()[:180]
        target = Decimal(str(data.get("target_price_br")))
        delay = int(data.get("eligibility_delay_seconds") or 0)
        expires = int(data.get("expires_after_seconds") or 0) or None
        score = int(data.get("minimum_intent_score") or 0)
        rule_type = str(data.get("rule_type") or "recovery").strip().lower()
        if rule_type not in {"recovery", "manual", "campaign"}:
            raise ValueError("Unsupported discount rule type")
        if not 0 <= score <= 1000:
            raise ValueError("minimum_intent_score must be between 0 and 1000")
        async with self.db.transaction() as conn:
            before = await conn.fetchrow("SELECT * FROM discount_rules WHERE id=$1 FOR UPDATE", rule_id)
            if before is None:
                raise LookupError("Discount rule not found")
            if int(before["revision"]) != int(expected_revision):
                raise ValueError("Discount rule changed in another session. Refresh before saving.")
            product = await conn.fetchrow("SELECT * FROM products WHERE id=$1", before["product_id"])
            if product is None:
                raise LookupError("Product not found")
            regular = Decimal(str(product["regular_price_br"]))
            if target <= 0 or target >= regular:
                raise ValueError("Recovery price must be positive and below regular price")
            row = await conn.fetchrow(
                """
                UPDATE discount_rules SET name=$2,rule_type=$3,target_price_br=$4,
                    eligibility_delay_seconds=$5,expires_after_seconds=$6,
                    require_no_pending_payment=$7,minimum_intent_score=$8,
                    revision=revision+1,updated_at=now()
                WHERE id=$1 RETURNING *
                """,
                rule_id, name, rule_type, target, delay, expires,
                bool(data.get("require_no_pending_payment", True)), score,
            )
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(
                conn, admin_id=admin_id, action="discount_rule.update",
                entity_type="discount_rule", entity_id=str(rule_id),
                before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)),
            )
        return dict(row)

    async def set_discount_rule_active(self, *, rule_id: UUID, admin_telegram_id: int, active: bool) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            before = await conn.fetchrow("SELECT * FROM discount_rules WHERE id=$1 FOR UPDATE", rule_id)
            if before is None:
                raise LookupError("Discount rule not found")
            row = await conn.fetchrow("UPDATE discount_rules SET is_active=$2,revision=revision+1,updated_at=now() WHERE id=$1 RETURNING *", rule_id, active)
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="discount_rule.enable" if active else "discount_rule.disable", entity_type="discount_rule", entity_id=str(rule_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def launch_campaign_offers(self, *, rule_id: UUID, admin_telegram_id: int) -> dict[str, Any]:
        """Bulk-create customer_offers for all eligible non-buyers using this discount rule."""
        async with self.db.transaction() as conn:
            rule = await conn.fetchrow("SELECT * FROM discount_rules WHERE id=$1 FOR UPDATE", rule_id)
            if rule is None:
                raise LookupError("Discount rule not found")
            if not rule["is_active"]:
                raise ValueError("Discount rule must be active to launch campaign offers")
            product = await conn.fetchrow("SELECT * FROM products WHERE id=$1", rule["product_id"])
            if product is None:
                raise LookupError("Product not found")
            if not product["discounts_enabled"]:
                raise ValueError("Product discounts are not enabled — enable them first")
            expires_seconds = int(rule["expires_after_seconds"] or 86400)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_seconds)
            original_price = Decimal(str(product["regular_price_br"]))
            offer_price = Decimal(str(rule["target_price_br"]))
            created = await self.repo.bulk_create_campaign_offers(
                conn,
                discount_rule_id=rule["id"],
                product_id=rule["product_id"],
                original_price_br=original_price,
                offer_price_br=offer_price,
                expires_at=expires_at,
            )
            # Enqueue a single bulk-expiry job for all offers tied to this rule.
            await self.jobs.enqueue_in_tx(conn, EnqueueJob(
                job_type="marketing.offer.expire",
                queue="automation",
                job_key=f"campaign:expire:{rule['id']}:{int(expires_at.timestamp())}",
                payload={"discount_rule_id": str(rule["id"]), "bulk": True},
                run_at=expires_at,
                priority=120,
                max_attempts=6,
            ))
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(
                conn, admin_id=admin_id,
                action="campaign_offers.launch", entity_type="discount_rule",
                entity_id=str(rule["id"]),
                after={"created": created, "offer_price_br": str(offer_price), "expires_at": expires_at.isoformat()},
            )
        return {"created": created, "rule_id": str(rule["id"]), "offer_price_br": str(offer_price), "expires_at": expires_at.isoformat()}

    async def preview_recovery_campaign(self, *, product_id: UUID | str | None = None) -> dict[str, Any]:
        """Provides preview reach and time data for the recovery campaign UI."""
        parsed_id: UUID | None = None
        if product_id:
            try:
                parsed_id = UUID(str(product_id).strip())
            except (ValueError, AttributeError):
                parsed_id = None

        async with self.db.acquire() as conn:
            if parsed_id:
                product = await conn.fetchrow(
                    """
                    SELECT p.id,p.slug,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,
                           COALESCE(am.title,en.title,p.slug) AS title,
                           COALESCE(am.title,p.slug) AS title_am, COALESCE(en.title,p.slug) AS title_en
                    FROM products p
                    LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
                    LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
                    WHERE p.id=$1
                    """,
                    parsed_id,
                )
            else:
                product = await conn.fetchrow(
                    """
                    SELECT p.id,p.slug,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,
                           COALESCE(am.title,en.title,p.slug) AS title,
                           COALESCE(am.title,p.slug) AS title_am, COALESCE(en.title,p.slug) AS title_en
                    FROM products p
                    LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
                    LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
                    ORDER BY (p.slug='ai-kezero') DESC, (p.status='active') DESC, p.created_at DESC
                    LIMIT 1
                    """
                )
            if product is None:
                raise LookupError("Product not found")

            prod_id = product["id"]
            non_buyers_count = await self.repo.audience_count(conn, normalize_audience({"kind": "non_buyers", "product_id": str(prod_id)}))
            high_intent_count = await self.repo.audience_count(conn, normalize_audience({"kind": "high_intent", "product_id": str(prod_id)}))

        now_utc = datetime.now(UTC)
        eat_offset = timedelta(hours=3)
        now_eat = now_utc + eat_offset
        midnight_eat = now_eat.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        midnight_utc = midnight_eat - eat_offset
        seconds_until_midnight = int((midnight_utc - now_utc).total_seconds())
        if seconds_until_midnight <= 0:
            seconds_until_midnight = 86400

        hours_remaining = round(seconds_until_midnight / 3600, 1)

        reg_price_raw = product["regular_price_br"]
        try:
            reg_price_display = str(int(Decimal(str(reg_price_raw)))) if reg_price_raw is not None else "549"
        except Exception:
            reg_price_display = "549"

        templates = get_recovery_campaign_templates(
            product_title_am=str(product["title_am"] or "AI ከዜሮ"),
            product_title_en=str(product["title_en"] or "AI From Zero"),
            regular_price_br=reg_price_display,
            offer_price_br="299",
            bot_url="https://t.me/...",
        )

        return {
            "product": {
                "id": str(prod_id),
                "title": product["title"],
                "regular_price_br": str(product["regular_price_br"] or "549.00"),
                "offer_price_br": "299.00",
            },
            "audience": {
                "non_buyers_count": non_buyers_count,
                "high_intent_count": high_intent_count,
            },
            "deadline": {
                "hours_remaining": hours_remaining,
                "expires_at": midnight_utc.isoformat(),
            },
            "stages": [
                {
                    "stage_key": t["stage_key"],
                    "name": t["name"],
                    "audience_kind": t["audience"]["kind"],
                    "relative_delay_minutes": t["relative_delay_minutes"],
                    "text_am": t["content_am"]["text"],
                    "text_en": t["content_en"]["text"],
                    "button_am": t["content_am"]["buttons"][0]["text"] if t["content_am"].get("buttons") else "",
                    "button_en": t["content_en"]["buttons"][0]["text"] if t["content_en"].get("buttons") else "",
                }
                for t in templates
            ],
        }

    async def launch_full_recovery_campaign(
        self,
        *,
        admin_telegram_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """1-click launcher for the 4-stage 299 Br recovery campaign."""
        product_id_raw = data.get("product_id")
        parsed_id: UUID | None = None
        if product_id_raw:
            try:
                parsed_id = UUID(str(product_id_raw).strip())
            except (ValueError, AttributeError):
                parsed_id = None

        async with self.db.acquire() as conn:
            if parsed_id:
                product = await conn.fetchrow(
                    """
                    SELECT p.id,p.slug,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,
                           COALESCE(am.title,en.title,p.slug) AS title,
                           COALESCE(am.title,p.slug) AS title_am, COALESCE(en.title,p.slug) AS title_en
                    FROM products p
                    LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
                    LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
                    WHERE p.id=$1
                    """,
                    parsed_id,
                )
            else:
                product = await conn.fetchrow(
                    """
                    SELECT p.id,p.slug,p.regular_price_br,p.recovery_price_br,p.discounts_enabled,
                           COALESCE(am.title,en.title,p.slug) AS title,
                           COALESCE(am.title,p.slug) AS title_am, COALESCE(en.title,p.slug) AS title_en
                    FROM products p
                    LEFT JOIN product_translations am ON am.product_id=p.id AND am.language='am'
                    LEFT JOIN product_translations en ON en.product_id=p.id AND en.language='en'
                    ORDER BY (p.slug='ai-kezero') DESC, (p.status='active') DESC, p.created_at DESC
                    LIMIT 1
                    """
                )
        if product is None:
            raise LookupError("Product not found")

        prod_id = product["id"]
        if not product["discounts_enabled"]:
            async with self.db.transaction() as conn:
                await conn.execute("UPDATE products SET discounts_enabled=TRUE WHERE id=$1", prod_id)

        now_utc = datetime.now(UTC)
        eat_offset = timedelta(hours=3)
        now_eat = now_utc + eat_offset
        midnight_eat = now_eat.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        midnight_utc = midnight_eat - eat_offset
        seconds_until_midnight = int((midnight_utc - now_utc).total_seconds())
        if seconds_until_midnight <= 0:
            seconds_until_midnight = 86400

        target_price = str(data.get("target_price_br") or "299.00")

        rule = await self.create_discount_rule(
            admin_telegram_id=admin_telegram_id,
            data={
                "product_id": str(prod_id),
                "name": f"Flash Recovery · {target_price} Br (Midnight EAT)",
                "rule_type": "campaign",
                "target_price_br": target_price,
                "expires_after_seconds": seconds_until_midnight,
                "is_active": True,
                "require_no_pending_payment": True,
                "minimum_intent_score": 0,
            },
        )
        rule_id = UUID(str(rule["id"]))

        launch_res = await self.launch_campaign_offers(rule_id=rule_id, admin_telegram_id=admin_telegram_id)
        offers_created = launch_res["created"]

        link = await self.create_tracking_link(
            admin_telegram_id=admin_telegram_id,
            data={
                "name": f"Recovery {target_price} Br Campaign {datetime.now(UTC).strftime('%Y-%m-%d')}",
                "product_id": str(prod_id),
                "platform": "telegram",
                "campaign": f"recovery-{int(Decimal(target_price))}-{datetime.now(UTC).strftime('%b%d').lower()}",
                "creative": "broadcast-image" if data.get("media_file_id") else "broadcast-text",
                "angle": "today-only-flash-sale",
            },
        )
        bot_url = link.get("bot_url", "")

        media = None
        media_file_id = str(data.get("media_file_id") or "").strip()
        media_type = str(data.get("media_type") or "photo").strip().lower()
        if media_file_id:
            media = {"type": media_type, "file_id": media_file_id}

        templates = get_recovery_campaign_templates(
            product_title_am=str(product["title_am"] or "AI ከዜሮ"),
            product_title_en=str(product["title_en"] or "AI From Zero"),
            regular_price_br=str(int(Decimal(str(product["regular_price_br"])))),
            offer_price_br=str(int(Decimal(target_price))),
            bot_url=bot_url,
            media=media,
        )

        scheduled_broadcasts: list[dict[str, Any]] = []
        for tpl in templates:
            bc = await self.create_broadcast(
                admin_telegram_id=admin_telegram_id,
                data={
                    "name": tpl["name"],
                    "audience_definition": {
                        "kind": tpl["audience"]["kind"],
                        "product_id": str(prod_id),
                    },
                    "content_am": tpl["content_am"],
                    "content_en": tpl["content_en"],
                },
            )
            if tpl["stage_key"] == "blast_1a":
                scheduled_time = now_utc
            elif tpl["stage_key"] == "blast_1b":
                scheduled_time = now_utc + timedelta(minutes=5)
            elif tpl["stage_key"] == "blast_2":
                scheduled_time = min(now_utc + timedelta(hours=4), max(now_utc + timedelta(minutes=15), midnight_utc - timedelta(hours=4)))
            elif tpl["stage_key"] == "blast_3":
                scheduled_time = min(now_utc + timedelta(hours=7), max(now_utc + timedelta(minutes=30), midnight_utc - timedelta(hours=1)))
            else:
                scheduled_time = now_utc + timedelta(minutes=tpl["relative_delay_minutes"])

            if scheduled_time < now_utc:
                scheduled_time = now_utc

            sched = await self.schedule_broadcast(
                broadcast_id=UUID(str(bc["id"])),
                admin_telegram_id=admin_telegram_id,
                scheduled_at=scheduled_time,
            )
            scheduled_broadcasts.append({
                "id": str(bc["id"]),
                "name": tpl["name"],
                "scheduled_at": scheduled_time.isoformat(),
                "recipients": sched.get("audience_snapshot_count", 0),
            })

        return {
            "success": True,
            "product": {
                "id": str(prod_id),
                "title": product["title"],
                "regular_price_br": str(product["regular_price_br"]),
                "offer_price_br": target_price,
            },
            "offers_created": offers_created,
            "rule_id": str(rule_id),
            "tracking_url": bot_url,
            "expires_at": launch_res["expires_at"],
            "broadcasts": scheduled_broadcasts,
        }

    async def create_tracking_link(self, *, admin_telegram_id: int, data: dict[str, Any]) -> dict[str, Any]:
        product_id = UUID(str(data["product_id"])) if data.get("product_id") else None
        language = data.get("language_hint") or None
        if language not in (None, "am", "en"):
            raise ValueError("language_hint must be am or en")
        token = ""
        async with self.db.transaction() as conn:
            if product_id and not await conn.fetchval("SELECT 1 FROM products WHERE id=$1", product_id):
                raise LookupError("Product not found")
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            for _ in range(8):
                token = secrets.token_urlsafe(6).replace("-", "_")[:12]
                if not await conn.fetchval("SELECT 1 FROM tracking_links WHERE token=$1", token):
                    break
            else:
                raise RuntimeError("Could not allocate tracking token")
            row = await conn.fetchrow(
                """
                INSERT INTO tracking_links(token,product_id,source,platform,campaign,ad_set,creative,angle,language_hint,is_active,metadata,label,created_by_admin_id)
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,TRUE,$10::jsonb,$11,$12) RETURNING *
                """,
                token, product_id, str(data.get("source") or "Meta")[:100], data.get("platform"), data.get("campaign"), data.get("ad_set"), data.get("creative"), data.get("angle"), language, dict(data.get("metadata") or {}), data.get("label"), admin_id,
            )
            await self.repo.audit(conn, admin_id=admin_id, action="tracking_link.create", entity_type="tracking_link", entity_id=str(row["id"]), after=jsonable_encoder(dict(row)))
        result = dict(row)
        result["bot_url"] = self._bot_start_url(token)
        return result

    async def set_tracking_link_active(self, *, link_id: UUID, admin_telegram_id: int, active: bool) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            before = await conn.fetchrow("SELECT * FROM tracking_links WHERE id=$1 FOR UPDATE", link_id)
            if before is None:
                raise LookupError("Tracking link not found")
            row = await conn.fetchrow("UPDATE tracking_links SET is_active=$2,revision=revision+1 WHERE id=$1 RETURNING *", link_id, active)
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await self.repo.audit(conn, admin_id=admin_id, action="tracking_link.enable" if active else "tracking_link.disable", entity_type="tracking_link", entity_id=str(link_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        result = dict(row); result["bot_url"] = self._bot_start_url(str(row["token"])); return result

    def _bot_start_url(self, token: str) -> str:
        username = self.settings.bot_username.strip().lstrip("@")
        return f"https://t.me/{username}?start=src_{token}" if username else f"?start=src_{token}"

    async def create_payout(self, *, referrer_user_id: UUID, admin_telegram_id: int, payout_method: str, payout_destination: str, note: str | None = None) -> dict[str, Any]:
        if payout_method not in {"cbe", "telebirr", "other"}:
            raise ValueError("Unsupported payout method")
        destination = payout_destination.strip()
        if not destination:
            raise ValueError("Payout destination is required")
        async with self.db.transaction() as conn:
            commissions = await conn.fetch(
                """
                SELECT c.* FROM commissions c
                WHERE c.referrer_user_id=$1 AND c.status='available'
                  AND NOT EXISTS (SELECT 1 FROM commission_payout_items i WHERE i.commission_id=c.id)
                ORDER BY c.available_at,c.created_at FOR UPDATE
                """,
                referrer_user_id,
            )
            if not commissions:
                raise ValueError("This partner has no available commission to pay")
            amount = sum((Decimal(str(c["amount_br"])) for c in commissions), Decimal("0.00"))
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            await conn.execute(
                """
                INSERT INTO referral_payout_profiles(user_id,payout_method,payout_destination,updated_at)
                VALUES($1,$2,$3,now())
                ON CONFLICT (user_id) DO UPDATE SET
                    payout_method=EXCLUDED.payout_method,
                    payout_destination=EXCLUDED.payout_destination,
                    updated_at=now()
                """,
                referrer_user_id, payout_method, destination,
            )
            payout = await conn.fetchrow(
                """
                INSERT INTO commission_payouts(referrer_user_id,amount_br,payout_method,payout_destination,status,note)
                VALUES($1,$2,$3,$4,'pending',$5) RETURNING *
                """,
                referrer_user_id, amount, payout_method, destination, note,
            )
            await conn.executemany(
                "INSERT INTO commission_payout_items(payout_id,commission_id,amount_br) VALUES($1,$2,$3)",
                [(payout["id"], c["id"], c["amount_br"]) for c in commissions],
            )
            await self.repo.audit(conn, admin_id=admin_id, action="referral_payout.create", entity_type="commission_payout", entity_id=str(payout["id"]), after=jsonable_encoder(dict(payout)))
        return dict(payout)

    async def mark_payout_paid(self, *, payout_id: UUID, admin_telegram_id: int, note: str | None = None) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            before = await conn.fetchrow("SELECT * FROM commission_payouts WHERE id=$1 FOR UPDATE", payout_id)
            if before is None:
                raise LookupError("Payout not found")
            if before["status"] == "paid":
                return dict(before)
            if before["status"] in {"cancelled", "failed"}:
                raise ValueError(f"Cannot mark a {before['status']} payout as paid")
            admin_id = await self.repo.admin_id(conn, admin_telegram_id)
            row = await conn.fetchrow(
                """UPDATE commission_payouts SET status='paid',processed_by_admin_id=$2,processed_at=now(),updated_at=now(),note=COALESCE($3,note) WHERE id=$1 RETURNING *""",
                payout_id, admin_id, note,
            )
            await conn.execute(
                """UPDATE commissions SET status='paid',paid_at=now(),updated_at=now() WHERE id IN (SELECT commission_id FROM commission_payout_items WHERE payout_id=$1)""",
                payout_id,
            )
            await self.repo.audit(conn, admin_id=admin_id, action="referral_payout.paid", entity_type="commission_payout", entity_id=str(payout_id), before=jsonable_encoder(dict(before)), after=jsonable_encoder(dict(row)))
        return dict(row)

    async def ensure_maintenance_job(self) -> None:
        async with self.db.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT 1 FROM jobs WHERE job_type='marketing.maintenance' AND status IN ('queued','running') LIMIT 1"
            )
        if exists:
            return
        due = datetime.now(UTC) + timedelta(seconds=self.settings.marketing_maintenance_interval_seconds)
        await self.jobs.enqueue(EnqueueJob(
            job_type="marketing.maintenance", queue="automation",
            job_key=f"marketing:maintenance:{int(due.timestamp())}", payload={}, run_at=due,
            priority=200, max_attempts=8,
        ))

    async def maintenance_tick(self) -> dict[str, int]:
        async with self.db.transaction() as conn:
            released = int((await conn.execute(
                "UPDATE commissions SET status='available',updated_at=now() WHERE status='pending' AND available_at IS NOT NULL AND available_at<=now()"
            )).split()[-1])
            expired = int((await conn.execute(
                "UPDATE customer_offers SET status='expired',updated_at=now() WHERE status IN ('scheduled','available') AND expires_at IS NOT NULL AND expires_at<=now()"
            )).split()[-1])
        due = datetime.now(UTC) + timedelta(seconds=self.settings.marketing_maintenance_interval_seconds)
        await self.jobs.enqueue(EnqueueJob(
            job_type="marketing.maintenance", queue="automation",
            job_key=f"marketing:maintenance:{int(due.timestamp())}", payload={}, run_at=due,
            priority=200, max_attempts=8,
        ))
        return {"commissions_released": released, "offers_expired": expired}

    async def trigger_automation_from_event(self, *, automation_id: UUID, event_id: int) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            automation = await self.repo.automation(conn, automation_id, for_update=True)
            event = await conn.fetchrow("SELECT * FROM events WHERE id=$1", event_id)
            if automation is None or event is None:
                return {"started": False, "reason": "missing"}
            if not automation["is_enabled"]:
                return {"started": False, "reason": "disabled"}
            if automation["trigger_event"] != event["event_type"]:
                return {"started": False, "reason": "trigger_mismatch"}
            if event["user_id"] is None:
                return {"started": False, "reason": "event_has_no_user"}
            if automation["product_id"] is not None and automation["product_id"] != event["product_id"]:
                return {"started": False, "reason": "product_mismatch"}
            audience = normalize_audience(dict(automation["audience_definition"] or {}))
            if not await self.repo.user_matches_audience(conn, user_id=event["user_id"], audience=audience):
                return {"started": False, "reason": "audience_mismatch"}
            product_id = automation["product_id"] or event["product_id"]
            cfg = dict(automation["trigger_config"] or {})
            if product_id and cfg.get("stop_on_purchase", True) and event["event_type"] not in {"PURCHASED", "PAYMENT_APPROVED"}:
                paid = await conn.fetchval(
                    """SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                       WHERE o.user_id=$1 AND oi.product_id=$2 AND o.status='paid' LIMIT 1""",
                    event["user_id"], product_id,
                )
                if paid:
                    return {"started": False, "reason": "already_purchased"}
            if product_id and cfg.get("stop_on_pending_payment", True):
                pending = await self._has_pending_payment(conn, user_id=event["user_id"], product_id=product_id)
                if pending:
                    return {"started": False, "reason": "pending_payment"}
            first = await conn.fetchrow(
                "SELECT * FROM automation_steps WHERE automation_id=$1 ORDER BY sort_order LIMIT 1",
                automation_id,
            )
            if first is None:
                return {"started": False, "reason": "no_steps"}
            run = await conn.fetchrow(
                """
                INSERT INTO automation_runs(automation_id,user_id,product_id,status,current_step_key,context,next_run_at,trigger_event_id)
                VALUES($1,$2,$3,'active',$4,$5::jsonb,now(),$6)
                ON CONFLICT (automation_id,user_id,trigger_event_id) WHERE trigger_event_id IS NOT NULL DO NOTHING
                RETURNING *
                """,
                automation_id, event["user_id"], product_id, first["step_key"],
                {"automation_version": automation["version"], "trigger_event": event["event_type"], "trigger_event_id": event_id},
                event_id,
            )
            if run is None:
                existing = await conn.fetchrow(
                    "SELECT * FROM automation_runs WHERE automation_id=$1 AND user_id=$2 AND trigger_event_id=$3",
                    automation_id, event["user_id"], event_id,
                )
                return {"started": False, "reason": "deduped", "run_id": str(existing["id"]) if existing else None}
            await self.jobs.enqueue_in_tx(conn, EnqueueJob(
                job_type="marketing.automation.step", queue="automation",
                job_key=f"automation:run:{run['id']}:step:{first['step_key']}",
                payload={"run_id": str(run["id"]), "step_key": first["step_key"]},
                priority=int(automation["priority"]), max_attempts=8,
            ))
        return {"started": True, "run_id": str(run["id"]), "step_key": first["step_key"]}

    async def execute_automation_step(self, *, run_id: UUID, step_key: str) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            run = await conn.fetchrow("SELECT * FROM automation_runs WHERE id=$1 FOR UPDATE", run_id)
            if run is None:
                return {"handled": False, "reason": "run_missing"}
            if run["status"] not in {"active", "waiting"}:
                return {"handled": False, "reason": f"run_{run['status']}"}
            if run["current_step_key"] != step_key:
                return {"handled": False, "reason": "stale_step"}
            automation = await self.repo.automation(conn, run["automation_id"])
            if automation is None or not automation["is_enabled"]:
                await self._stop_run(conn, run_id=run_id, reason="automation_disabled")
                return {"handled": True, "stopped": "automation_disabled"}
            step = await conn.fetchrow(
                "SELECT * FROM automation_steps WHERE automation_id=$1 AND step_key=$2",
                run["automation_id"], step_key,
            )
            if step is None:
                await self._stop_run(conn, run_id=run_id, reason="step_missing")
                return {"handled": True, "stopped": "step_missing"}
            product_id = run["product_id"]
            trigger_event = str(dict(run["context"] or {}).get("trigger_event") or "")
            cfg = dict(automation["trigger_config"] or {})
            if product_id and cfg.get("stop_on_purchase", True) and trigger_event not in {"PURCHASED", "PAYMENT_APPROVED"}:
                paid = await conn.fetchval(
                    """SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
                       WHERE o.user_id=$1 AND oi.product_id=$2 AND o.status='paid' LIMIT 1""",
                    run["user_id"], product_id,
                )
                if paid:
                    await self._stop_run(conn, run_id=run_id, reason="purchase")
                    return {"handled": True, "stopped": "purchase"}
            if product_id and cfg.get("stop_on_pending_payment", True) and step["step_type"] in {"send_message", "create_offer"}:
                if await self._has_pending_payment(conn, user_id=run["user_id"], product_id=product_id):
                    await self._stop_run(conn, run_id=run_id, reason="pending_payment")
                    return {"handled": True, "stopped": "pending_payment"}

            await conn.execute("UPDATE automation_runs SET last_step_started_at=now(),updated_at=now() WHERE id=$1", run_id)
            config = dict(step["config"] or {})
            step_type = step["step_type"]
            next_step = await conn.fetchrow(
                "SELECT * FROM automation_steps WHERE automation_id=$1 AND sort_order>$2 ORDER BY sort_order LIMIT 1",
                run["automation_id"], step["sort_order"],
            )

            if step_type == "wait":
                if next_step is None:
                    await self._complete_run(conn, run_id=run_id)
                    return {"handled": True, "completed": True}
                due = datetime.now(UTC) + timedelta(seconds=int(config["seconds"]))
                await self._queue_next_step(conn, run=run, next_step=next_step, due=due, priority=int(automation["priority"]))
                return {"handled": True, "waiting_until": due.isoformat()}

            if step_type == "send_message":
                await self.jobs.enqueue_in_tx(conn, EnqueueJob(
                    job_type="marketing.automation.message", queue="telegram",
                    job_key=f"automation:message:{run_id}:{step_key}",
                    payload={"run_id": str(run_id), "step_key": step_key},
                    priority=80, max_attempts=8,
                ))
                await self._advance_or_complete(conn, run=run, next_step=next_step, priority=int(automation["priority"]))
                return {"handled": True, "message_queued": True}

            if step_type == "condition":
                passed = await self._evaluate_condition(conn, run=run, config=config)
                if not passed:
                    await self._stop_run(conn, run_id=run_id, reason=f"condition_failed:{config['condition']}")
                    return {"handled": True, "condition": config["condition"], "passed": False}
                await self._advance_or_complete(conn, run=run, next_step=next_step, priority=int(automation["priority"]))
                return {"handled": True, "condition": config["condition"], "passed": True}

            if step_type == "create_offer":
                offer = await self._create_recovery_offer(conn, run=run, config=config)
                await self._advance_or_complete(conn, run=run, next_step=next_step, priority=int(automation["priority"]))
                return {"handled": True, "offer_id": str(offer["id"]) if offer else None}

            if step_type == "expire_offer":
                count = int((await conn.execute(
                    "UPDATE customer_offers SET status='expired',updated_at=now() WHERE automation_run_id=$1 AND status IN ('scheduled','available')",
                    run_id,
                )).split()[-1])
                await self._advance_or_complete(conn, run=run, next_step=next_step, priority=int(automation["priority"]))
                return {"handled": True, "offers_expired": count}

            if step_type == "stop":
                await self._stop_run(conn, run_id=run_id, reason=str(config.get("reason") or "completed"))
                return {"handled": True, "stopped": str(config.get("reason") or "completed")}

            await self._stop_run(conn, run_id=run_id, reason="unsupported_step")
            return {"handled": True, "stopped": "unsupported_step"}

    async def expire_offer(self, *, offer_id: UUID) -> dict[str, Any]:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow("SELECT * FROM customer_offers WHERE id=$1 FOR UPDATE", offer_id)
            if row is None:
                return {"changed": False, "reason": "missing"}
            if row["status"] not in {"scheduled", "available"}:
                return {"changed": False, "status": row["status"]}
            if row["expires_at"] and row["expires_at"] > datetime.now(UTC):
                await self.jobs.enqueue_in_tx(conn, EnqueueJob(
                    job_type="marketing.offer.expire", queue="automation",
                    job_key=f"offer:expire:{offer_id}:{int(row['expires_at'].timestamp())}",
                    payload={"offer_id": str(offer_id)}, run_at=row["expires_at"], priority=120, max_attempts=6,
                ))
                return {"changed": False, "reason": "not_due"}
            updated = await conn.fetchrow("UPDATE customer_offers SET status='expired',updated_at=now() WHERE id=$1 RETURNING *", offer_id)
        return {"changed": True, "offer_id": str(offer_id), "status": updated["status"]}

    async def _has_pending_payment(self, conn: Any, *, user_id: Any, product_id: Any) -> bool:
        return bool(await conn.fetchval(
            """
            SELECT 1 FROM payments p
            JOIN orders o ON o.id=p.order_id JOIN order_items oi ON oi.order_id=o.id
            WHERE p.user_id=$1 AND oi.product_id=$2
              AND p.status IN ('awaiting_proof','pending_review','flagged')
              AND o.status IN ('created','awaiting_payment','proof_submitted','under_review','needs_new_proof')
            LIMIT 1
            """,
            user_id, product_id,
        ))

    async def _queue_next_step(self, conn: Any, *, run: Any, next_step: Any, due: datetime, priority: int) -> None:
        await conn.execute(
            "UPDATE automation_runs SET status='waiting',current_step_key=$2,next_run_at=$3,updated_at=now() WHERE id=$1",
            run["id"], next_step["step_key"], due,
        )
        await self.jobs.enqueue_in_tx(conn, EnqueueJob(
            job_type="marketing.automation.step", queue="automation",
            job_key=f"automation:run:{run['id']}:step:{next_step['step_key']}",
            payload={"run_id": str(run["id"]), "step_key": next_step["step_key"]},
            run_at=due, priority=priority, max_attempts=8,
        ))

    async def _advance_or_complete(self, conn: Any, *, run: Any, next_step: Any | None, priority: int) -> None:
        if next_step is None:
            await self._complete_run(conn, run_id=run["id"])
            return
        await conn.execute(
            "UPDATE automation_runs SET status='active',current_step_key=$2,next_run_at=now(),updated_at=now() WHERE id=$1",
            run["id"], next_step["step_key"],
        )
        await self.jobs.enqueue_in_tx(conn, EnqueueJob(
            job_type="marketing.automation.step", queue="automation",
            job_key=f"automation:run:{run['id']}:step:{next_step['step_key']}",
            payload={"run_id": str(run["id"]), "step_key": next_step["step_key"]},
            priority=priority, max_attempts=8,
        ))

    async def _complete_run(self, conn: Any, *, run_id: UUID) -> None:
        await conn.execute(
            "UPDATE automation_runs SET status='completed',completed_at=now(),next_run_at=NULL,updated_at=now() WHERE id=$1",
            run_id,
        )

    async def _stop_run(self, conn: Any, *, run_id: UUID, reason: str) -> None:
        await conn.execute(
            "UPDATE automation_runs SET status='stopped',stop_reason=$2,completed_at=now(),next_run_at=NULL,updated_at=now() WHERE id=$1",
            run_id, reason[:180],
        )

    async def _evaluate_condition(self, conn: Any, *, run: Any, config: dict[str, Any]) -> bool:
        condition = config["condition"]
        product_id = run["product_id"]
        if condition == "not_purchased":
            if product_id is None:
                return True
            return not bool(await conn.fetchval(
                "SELECT 1 FROM entitlements WHERE user_id=$1 AND product_id=$2 AND revoked_at IS NULL LIMIT 1",
                run["user_id"], product_id,
            ))
        if condition == "no_pending_payment":
            return True if product_id is None else not await self._has_pending_payment(conn, user_id=run["user_id"], product_id=product_id)
        if condition == "has_not_active_offer":
            if product_id is None:
                return True
            return not bool(await conn.fetchval(
                "SELECT 1 FROM customer_offers WHERE user_id=$1 AND product_id=$2 AND status IN ('scheduled','available') LIMIT 1",
                run["user_id"], product_id,
            ))
        if condition == "intent_at_least":
            if product_id is None:
                return False
            score = await conn.fetchval("SELECT intent_score FROM user_product_journeys WHERE user_id=$1 AND product_id=$2", run["user_id"], product_id)
            return int(score or 0) >= int(config.get("score") or 0)
        return False

    async def _create_recovery_offer(self, conn: Any, *, run: Any, config: dict[str, Any]) -> Any | None:
        product_id = run["product_id"]
        if product_id is None:
            raise ValueError("Recovery offer step requires a product-scoped automation")
        if await conn.fetchval(
            """SELECT 1 FROM orders o JOIN order_items oi ON oi.order_id=o.id
               WHERE o.user_id=$1 AND oi.product_id=$2 AND o.status='paid' LIMIT 1""",
            run["user_id"], product_id,
        ):
            await self._stop_run(conn, run_id=run["id"], reason="purchase")
            return None
        if await self._has_pending_payment(conn, user_id=run["user_id"], product_id=product_id):
            await self._stop_run(conn, run_id=run["id"], reason="pending_payment")
            return None
        existing = await conn.fetchrow(
            "SELECT * FROM customer_offers WHERE user_id=$1 AND product_id=$2 AND status IN ('scheduled','available') FOR UPDATE",
            run["user_id"], product_id,
        )
        if existing is not None:
            return existing
        product = await conn.fetchrow("SELECT * FROM products WHERE id=$1 FOR UPDATE", product_id)
        if product is None or not product["discounts_enabled"]:
            raise ValueError("Product recovery discounts are disabled")
        regular = Decimal(str(product["regular_price_br"]))
        price = Decimal(str(config.get("price_br") or product["recovery_price_br"] or "0"))
        if price <= 0 or price >= regular:
            raise ValueError("Recovery automation needs a valid discounted price")
        rule = await conn.fetchrow(
            "SELECT * FROM discount_rules WHERE product_id=$1 AND is_active=TRUE AND rule_type='recovery' ORDER BY updated_at DESC LIMIT 1",
            product_id,
        )
        if rule and rule["require_no_pending_payment"] and await self._has_pending_payment(conn, user_id=run["user_id"], product_id=product_id):
            return None
        if rule and int(rule["minimum_intent_score"] or 0) > 0:
            score = int(await conn.fetchval("SELECT intent_score FROM user_product_journeys WHERE user_id=$1 AND product_id=$2", run["user_id"], product_id) or 0)
            if score < int(rule["minimum_intent_score"]):
                return None
        expires_after = int(config.get("expires_after_seconds") or (rule["expires_after_seconds"] if rule else 86400) or 86400)
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_after)
        offer = await conn.fetchrow(
            """
            INSERT INTO customer_offers(user_id,product_id,discount_rule_id,original_price_br,offer_price_br,status,eligible_at,starts_at,expires_at,automation_run_id)
            VALUES($1,$2,$3,$4,$5,'available',now(),now(),$6,$7) RETURNING *
            """,
            run["user_id"], product_id, rule["id"] if rule else None, regular, price, expires_at, run["id"],
        )
        await self.events.append(
            conn, event_type="DISCOUNT_UNLOCKED", user_id=run["user_id"], product_id=product_id,
            payload={"offer_id": str(offer["id"]), "original_price_br": str(regular), "offer_price_br": str(price), "commissionable": False},
        )
        await self.jobs.enqueue_in_tx(conn, EnqueueJob(
            job_type="marketing.offer.expire", queue="automation",
            job_key=f"offer:expire:{offer['id']}:{int(expires_at.timestamp())}",
            payload={"offer_id": str(offer["id"])}, run_at=expires_at, priority=120, max_attempts=6,
        ))
        return offer
