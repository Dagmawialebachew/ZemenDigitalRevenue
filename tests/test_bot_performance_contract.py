from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_customer_context_is_loaded_in_one_joined_query() -> None:
    source = (ROOT / "bot/services/current_user.py").read_text(encoding="utf-8")

    assert source.count("await conn.fetchrow(") == 1
    assert "LEFT JOIN user_profiles" in source
    assert "LEFT JOIN conversation_sessions" in source
    assert "LEFT JOIN products" in source
    assert "UserRepository" not in source


def test_sales_reads_include_ownership_without_an_extra_checkout_chain() -> None:
    service = (ROOT / "backend/services/salesman.py").read_text(encoding="utf-8")
    router = (ROOT / "bot/routers/sales.py").read_text(encoding="utf-8")

    assert "AS is_owned" in service
    assert "presentation.is_owned" in router
    assert "await service.owns_focused_product" not in router
    assert "PaymentRepository" not in service


def test_sales_telemetry_runs_after_customer_facing_messages() -> None:
    router = (ROOT / "bot/routers/sales.py").read_text(encoding="utf-8")

    assert "run_background(" in router
    assert "service.record_pitch_view(presentation)" in router
    assert "service.record_detail_view(detail, kind=kind)" in router


def test_telegram_and_pool_latency_are_observable() -> None:
    telegram = (ROOT / "backend/api/routes/telegram.py").read_text(encoding="utf-8")
    pool = (ROOT / "backend/db/pool.py").read_text(encoding="utf-8")

    assert "telegram_update_slow" in telegram
    assert "elapsed_ms" in telegram
    assert "database_pool_slow_acquire" in pool
