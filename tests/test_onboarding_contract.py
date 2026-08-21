from pathlib import Path

from backend.domain.sales import SalesProfile
from bot.services.onboarding_copy import question_text


def test_product_campaign_onboarding_precedes_sales_pitch():
    factory = Path("bot/factory.py").read_text(encoding="utf-8")
    language = Path("bot/routers/language.py").read_text(encoding="utf-8")
    start = Path("bot/routers/start.py").read_text(encoding="utf-8")
    assert "onboarding_router" in factory
    assert "sales_router" in factory
    current_user = Path("bot/services/current_user.py").read_text(encoding="utf-8")
    customer_entry = Path("backend/services/customer_entry.py").read_text(encoding="utf-8")

    assert "requires_onboarding_before_sales" in start
    assert "entry.product_campaign_entry" in start
    assert "send_onboarding_step" in start
    assert "requires_onboarding_before_sales" in language
    assert "send_onboarding_step" in language
    assert "tracking_product_id" in current_user
    assert "including the users acquired before this routing fix" in customer_entry
    assert 'callback_data="sales:continue"' in Path("bot/keyboards/sales.py").read_text(
        encoding="utf-8"
    )
    assert "if not entry.profile_completed" in start


def test_s05_onboarding_uses_persistent_service_not_fsm():
    router = Path("bot/routers/onboarding.py").read_text(encoding="utf-8")
    service = Path("backend/services/onboarding.py").read_text(encoding="utf-8")
    assert "OnboardingService" in router
    assert "conversation_sessions" not in router
    assert "ONBOARDING_COMPLETED" in service


def test_campaign_onboarding_intro_anchors_the_product_and_escapes_html():
    text = question_text(
        field="role",
        language="en",
        profile=SalesProfile(),
        campaign_product_title="AI <From Zero>",
    )

    assert "AI &lt;From Zero&gt; is ready for you" in text
    assert "less than 30 seconds" in text
    assert "1/4" in text
