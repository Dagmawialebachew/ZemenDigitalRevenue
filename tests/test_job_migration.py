from pathlib import Path


def test_s03_job_migration_contains_durable_queue_invariants() -> None:
    sql = Path("database/migrations/0004_job_engine.sql").read_text(encoding="utf-8")
    for token in (
        "lease_expires_at",
        "job_attempts",
        "pg_notify('zemen_jobs'",
        "idx_jobs_due",
        "idx_jobs_stale",
        "UNIQUE (job_id, attempt_no)",
    ):
        assert token in sql
