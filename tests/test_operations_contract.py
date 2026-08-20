from pathlib import Path

from backend.core.config import Settings


def test_s08_worker_registry_contains_operations_jobs():
    source = Path("workers/handlers/__init__.py").read_text(encoding="utf-8")
    assert "operations.maintenance" in source
    assert "telegram.ops.alert" in source
    assert "telegram.ops.support_case" in source
    assert "telegram.delivery.product" in source


def test_operations_settings_are_guarded():
    s = Settings(
        workers_enabled=False,
        ops_maintenance_interval_seconds=5,
        delivery_job_max_attempts=5,
        delivery_max_total_attempts=4,
    )
    errors = s.runtime_errors()
    assert "OPS_MAINTENANCE_INTERVAL_SECONDS must be >= 15" in errors
    assert "DELIVERY_MAX_TOTAL_ATTEMPTS must be >= DELIVERY_JOB_MAX_ATTEMPTS" in errors


def test_support_router_uses_persistent_reply_context_and_fallback_is_last():
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    menu = Path("bot/routers/menu.py").read_text(encoding="utf-8")
    support = Path("bot/routers/support.py").read_text(encoding="utf-8")
    fallback = Path("bot/routers/fallback.py").read_text(encoding="utf-8")

    assert "support_router" in factory
    assert "fallback_router" in factory

    assert "menu:help" not in menu
    assert 'F.data == "menu:help"' in support

    assert "ops:support:reply:" in support
    assert "ops:support:resolve:" in support

    assert "support_reply_contexts" in support
    assert "SUPPORT_REPLY_CONTEXT" not in support
    assert "ForceReply" not in support

    assert 'Router(name="fallback")' in fallback
    assert "open_support" in fallback
    assert "submit_support_message" in fallback
    assert 'F.chat.type == "private"' in fallback

    include_start = factory.index("dp.include_routers(")
    include_block = factory[include_start:]
    assert include_block.rfind("fallback_router") > include_block.rfind("menu_router")
    assert include_block.rfind("fallback_router") > include_block.rfind("support_router")
    assert include_block.rfind("fallback_router") > include_block.rfind("payments_router")


def test_support_reply_context_migration_exists():
    migrations = sorted(Path("database/migrations").glob("0013_*.sql"))
    assert migrations, "0013 support reply context migration is missing"

    source = migrations[0].read_text(encoding="utf-8")
    assert "support_reply_contexts" in source
    assert "admin_telegram_id" in source
    assert "case_id" in source
    assert "ops_chat_id" in source
    assert "message_thread_id" in source
    assert "expires_at" in source


def test_migration_runner_uses_canonical_database_directory_and_has_cli_entrypoint():
    source = Path("scripts/migrate.py").read_text(encoding="utf-8")
    assert '"database" / "migrations"' in source
    assert 'if __name__ == "__main__":' in source
    assert "asyncio.run(_main())" in source


def test_payment_media_can_fall_through_to_support():
    source = Path("bot/routers/payments.py").read_text(encoding="utf-8")

    assert "SkipHandler" in source
    assert "raise SkipHandler" in source
    assert "@router.message(F.photo)" in source
    assert "F.document" in source


def test_resolving_support_clears_pending_admin_reply_context():
    source = Path("backend/services/operations.py").read_text(encoding="utf-8")
    assert "DELETE FROM support_reply_contexts WHERE case_id=$1" in source
    assert "step_key='home'" in source
    assert "SUPPORT_RESOLVED" in source


def test_terminal_job_failure_surfaces_ops_alert():
    engine = Path("workers/engine.py").read_text(encoding="utf-8")
    assert "job_failure_alerts_enabled" in engine
    assert "job_terminal_failure" in engine
    assert "telegram.ops.alert" in engine
    assert 'job.job_type != "telegram.ops.alert"' in engine


def test_delivery_handler_records_attempts_and_final_failure():
    source = Path("workers/handlers/payments.py").read_text(encoding="utf-8")
    assert "begin_delivery_attempt" in source
    assert "finish_delivery_attempt" in source
    assert "mark_delivery_failed" in source
    assert "job.final_attempt" in source


def test_ops_api_is_bearer_protected():
    security = Path("backend/security/ops.py").read_text(encoding="utf-8")
    routes = Path("backend/api/routes/operations.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in security
    assert "OPS_API_KEY" in security
    assert "dependencies=[Depends(require_ops_api)]" in routes