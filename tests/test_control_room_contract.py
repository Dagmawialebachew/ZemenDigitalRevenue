from pathlib import Path

from backend.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_control_origins_parse_and_cookie_settings():
    s = Settings(
        control_allowed_origins="http://localhost:5174,https://control.example.com/",
        control_session_ttl_seconds=600,
    )
    assert s.control_allowed_origins == ("http://localhost:5174", "https://control.example.com")
    assert s.control_cookie_name == "zemen_control_session"


def test_control_routes_are_cookie_authenticated_and_financial_actions_exist():
    text = (ROOT / "backend/api/routes/control.py").read_text(encoding="utf-8")
    assert "httponly=True" in text
    assert "require_control_session" in text
    assert '/payments/{payment_public_id}/approve' in text
    assert '/payments/{payment_public_id}/reject' in text
    assert '/payments/{payment_public_id}/flag' in text
    assert "payment-proofs/{proof_id}/image" in text
    assert "await bot.download" in text


def test_control_cors_supports_authenticated_dashboard_cookie():
    text = (ROOT / "backend/app.py").read_text(encoding="utf-8")
    assert "control_allowed_origins" in text
    assert "allow_credentials=True" in text


def test_control_room_query_indexes_exist():
    text = (ROOT / "database/migrations/0009_control_room_indexes.sql").read_text(encoding="utf-8")
    for index in (
        "idx_orders_control_paid", "idx_users_control_stage_seen",
        "idx_events_control_time_type", "idx_support_cases_control_queue",
    ):
        assert index in text


def test_dashboard_is_zemen_palette_not_hilawe_cyber_palette():
    css = (ROOT / "dashboard/src/styles.css").read_text(encoding="utf-8").lower()
    assert "--green:#8bdf31" in css
    assert "--ivory:#f3f0e7" in css
    assert "brand-cyan" not in css
    assert "brand-gold" not in css
    app = (ROOT / "dashboard/src/App.tsx").read_text(encoding="utf-8")
    assert "ZEMEN" in app and "CONTROL" in app
    assert "Neural" not in app and "Uplink" not in app and "Deploy Product" not in app


def test_s09_still_has_no_redis_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "redis" not in requirements
    assert "redis" not in pyproject
