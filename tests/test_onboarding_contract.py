from pathlib import Path


def test_s05_router_is_registered_and_language_enters_onboarding():
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    language = Path("bot/routers/language.py").read_text(encoding="utf-8")
    start = Path("bot/routers/start.py").read_text(encoding="utf-8")
    assert "onboarding_router" in factory
    assert "sales_router" in factory
    assert "send_onboarding_step" in language
    assert "if not entry.profile_completed" in start


def test_s05_onboarding_uses_persistent_service_not_fsm():
    router = Path("bot/routers/onboarding.py").read_text(encoding="utf-8")
    service = Path("backend/services/onboarding.py").read_text(encoding="utf-8")
    assert "OnboardingService" in router
    assert "conversation_sessions" not in router
    assert "ONBOARDING_COMPLETED" in service
