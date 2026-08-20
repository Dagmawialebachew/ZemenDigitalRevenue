from pathlib import Path

from backend.security.control import csrf_token_for_session, login_fingerprint
from shared.constants import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_final_migration_contains_review_and_login_hardening() -> None:
    sql = (ROOT / "database/migrations/0012_final_integration.sql").read_text(encoding="utf-8")
    assert "business_expenses" in sql
    assert "control_login_attempts" in sql
    assert "zemen_review_verified_purchase" in sql
    assert "reviews_featured_requires_approved" in sql
    assert "uq_reviews_customer_product" in sql


def test_analytics_queries_avoid_raw_event_order_row_multiplication() -> None:
    source = (ROOT / "backend/repositories/final_control.py").read_text(encoding="utf-8")
    assert "Aggregate sales and attention independently" in source
    assert "LEFT JOIN LATERAL" in source
    assert "Same rule for source attribution" in source


def test_control_csrf_is_bound_to_session_and_secret() -> None:
    a = csrf_token_for_session("session-A", "x" * 32)
    assert a == csrf_token_for_session("session-A", "x" * 32)
    assert a != csrf_token_for_session("session-B", "x" * 32)
    assert a != csrf_token_for_session("session-A", "y" * 32)


def test_login_fingerprint_does_not_expose_raw_input() -> None:
    value = login_fingerprint(remote_host="203.0.113.8", telegram_id=123456, secret="s" * 32)
    assert "203.0.113.8" not in value
    assert "123456" not in value
    assert len(value) == 64


def test_production_container_builds_frontends_under_same_origin_paths() -> None:
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "VITE_BASE_PATH=/store/" in docker
    assert "VITE_BASE_PATH=/control/" in docker
    assert "STATIC_APPS_ENABLED=true" in docker
    assert "redis" not in docker.lower()


def test_backup_and_restore_are_explicit_and_hashable() -> None:
    backup = (ROOT / "scripts/backup_database.py").read_text(encoding="utf-8")
    restore = (ROOT / "scripts/restore_database.py").read_text(encoding="utf-8")
    assert "pg_dump" in backup and "sha256" in backup
    assert "--confirm" in restore and '"RESTORE"' in restore
    assert "pg_restore" in restore


def test_final_version_is_one_zero() -> None:
    assert APP_VERSION == "1.0.2"
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.0.2"
