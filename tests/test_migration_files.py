from pathlib import Path


def test_migrations_are_sequential_and_present() -> None:
    names = sorted(path.name for path in Path("database/migrations").glob("*.sql"))
    assert names[:3] == [
        "0001_core_schema.sql",
        "0002_invariants_indexes.sql",
        "0003_seed_system_defaults.sql",
    ]


def test_discount_commission_invariant_exists_in_sql() -> None:
    sql = Path("database/migrations/0002_invariants_indexes.sql").read_text(encoding="utf-8")
    assert "Discounted orders cannot generate referral commission" in sql
    assert "enforce_commission_eligibility" in sql


def test_repeated_user_source_index_is_guarded() -> None:
    sql = Path("database/migrations/0005_salesman_core.sql").read_text(encoding="utf-8")
    assert "CREATE INDEX IF NOT EXISTS idx_user_sources_user_created" in sql
