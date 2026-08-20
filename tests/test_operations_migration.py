from pathlib import Path


def test_operations_migration_has_durable_delivery_and_alerts():
    sql = Path('database/migrations/0008_operations_hardening.sql').read_text(encoding="utf-8")
    assert 'CREATE TABLE delivery_attempts' in sql
    assert 'CREATE TABLE operational_alerts' in sql
    assert 'CREATE TABLE support_ops_messages' in sql
    assert 'delivery_attempt_count' in sql
    assert 'uq_support_live_context' in sql


def test_operations_migration_indexes_payment_age_and_delivery_queue():
    sql = Path('database/migrations/0008_operations_hardening.sql').read_text(encoding="utf-8")
    assert 'idx_payments_review_age' in sql
    assert 'idx_entitlements_delivery_queue' in sql
