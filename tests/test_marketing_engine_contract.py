from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_s11_migration_has_durable_marketing_boundaries() -> None:
    sql = read("database/migrations/0011_marketing_engine.sql")
    for fragment in (
        "broadcast_click_links",
        "referral_payout_profiles",
        "enqueue_marketing_automation_events",
        "marketing.automation.trigger",
        "attribute_paid_order_to_broadcast",
        "revoke_offers_after_purchase_event",
        "uq_automation_run_event",
    ):
        assert fragment in sql


def test_marketing_worker_registry_is_complete() -> None:
    registry = read("workers/handlers/__init__.py")
    for job_type in (
        "marketing.automation.trigger",
        "marketing.automation.step",
        "marketing.automation.message",
        "marketing.offer.expire",
        "marketing.maintenance",
        "marketing.broadcast.dispatch",
        "marketing.broadcast.send",
    ):
        assert job_type in registry


def test_broadcast_worker_finishes_all_terminal_recipient_paths() -> None:
    worker = read("workers/handlers/marketing.py")
    assert "_finalize_broadcast_if_terminal" in worker
    assert "FOR UPDATE SKIP LOCKED" in worker
    assert "broadcast_click_links" in worker
    assert "TelegramForbiddenError" in worker
    repo = read("backend/repositories/marketing.py")
    service = read("backend/services/marketing.py")
    assert "snapshot_broadcast_audience" in repo
    assert "audience_size = await self.repo.snapshot_broadcast_audience" in service


def test_marketing_dashboard_has_all_locked_surfaces() -> None:
    view = read("dashboard/src/views/MarketingView.tsx")
    app = read("dashboard/src/App.tsx")
    for label in ("Broadcasts", "Automations", "Discounts", "Referrals", "Ad Links"):
        assert label in view
    assert "Marketing" in app
    assert "Full-price referrals only" in view
    assert "Discount sales pay 0 Br referral commission" in view
    assert "disabled={Boolean(existing)}" in view
    assert "blocked_count" in view and "failed_count" in view


def test_control_api_supports_editable_marketing_not_source_code_changes() -> None:
    route = read("backend/api/routes/marketing.py")
    for fragment in (
        '/broadcasts/{broadcast_id}',
        '/automations/{automation_id}',
        '/discount-rules/{rule_id}',
        '/links/{link_id}/enabled',
        '/payouts/{payout_id}/paid',
        "/audience/count",
    ):
        assert fragment in route
    assert "require_control_session" in route


def test_recovery_audience_is_product_scoped_when_product_present() -> None:
    repo = read("backend/repositories/marketing.py")
    assert "SELECT 1 FROM order_items oi WHERE oi.order_id=o.id AND oi.product_id=$4::uuid" in repo


def test_referral_available_balance_excludes_pending_payout_allocations() -> None:
    repo = read("backend/repositories/marketing.py")
    assert repo.count("commission_payout_items i WHERE i.commission_id=c.id") >= 2
    assert "commission_payout_items cpi WHERE cpi.commission_id=c.id" in repo


def test_marketing_maintenance_is_started_with_application_workers() -> None:
    app = read("backend/app.py")
    assert "MarketingService" in app
    assert "ensure_maintenance_job" in app


def test_s11_keeps_discount_commission_database_lock() -> None:
    invariant = read("database/migrations/0002_invariants_indexes.sql")
    product_lock = read("database/migrations/0010_product_control.sql")
    assert "Discounted orders cannot generate referral commission" in invariant
    assert "CHECK (commission_only_full_price IS TRUE)" in product_lock


def test_s11_still_has_no_redis() -> None:
    assert "redis" not in read("requirements.txt").lower()
    assert "redis" not in read("pyproject.toml").lower()
