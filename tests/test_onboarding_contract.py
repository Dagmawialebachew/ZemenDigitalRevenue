from pathlib import Path


def test_s05_router_is_registered_and_product_value_precedes_optional_onboarding():
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    language = Path("bot/routers/language.py").read_text(encoding="utf-8")
    start = Path("bot/routers/start.py").read_text(encoding="utf-8")
    assert "onboarding_router" in factory
    assert "sales_router" in factory
    assert "send_sales_pitch" in language
    assert 'callback_data="sales:continue"' in Path("bot/keyboards/sales.py").read_text(encoding="utf-8")
    assert "if not entry.profile_completed" in start


def test_s05_onboarding_uses_persistent_service_not_fsm():
    router = Path("bot/routers/onboarding.py").read_text(encoding="utf-8")
    service = Path("backend/services/onboarding.py").read_text(encoding="utf-8")
    assert "OnboardingService" in router
    assert "conversation_sessions" not in router
    assert "ONBOARDING_COMPLETED" in service
