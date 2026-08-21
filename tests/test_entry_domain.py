from backend.domain.entry import (
    is_product_campaign_entry,
    requires_product_campaign_onboarding,
    should_notify_new_user,
    source_touch_type,
)


def test_resolved_new_source_is_first_touch() -> None:
    assert source_touch_type(is_new_user=True, resolved=True) == "first"


def test_resolved_returning_source_is_revisit() -> None:
    assert source_touch_type(is_new_user=False, resolved=True) == "revisit"


def test_unresolved_token_never_becomes_trusted_first_touch() -> None:
    assert source_touch_type(is_new_user=True, resolved=False) == "organic"


def test_new_user_ops_notification_contract() -> None:
    assert should_notify_new_user(is_new_user=True) is True
    assert should_notify_new_user(is_new_user=False) is False


def test_only_incomplete_product_campaign_visitors_require_onboarding() -> None:
    assert is_product_campaign_entry(
        tracking_product_id="campaign-product",
        focus_product_id="focused-product",
    )
    assert requires_product_campaign_onboarding(
        profile_completed=False,
        tracking_product_id="campaign-product",
        focus_product_id="focused-product",
    )
    assert not requires_product_campaign_onboarding(
        profile_completed=True,
        tracking_product_id="campaign-product",
        focus_product_id="focused-product",
    )
    assert not requires_product_campaign_onboarding(
        profile_completed=False,
        tracking_product_id=None,
        focus_product_id="organic-product",
    )
