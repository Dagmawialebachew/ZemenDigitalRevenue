from __future__ import annotations

from enum import StrEnum


class EntryChannel(StrEnum):
    SOURCE = "source"
    REFERRAL = "referral"
    ORGANIC = "organic"
    UNKNOWN = "unknown"


def source_touch_type(*, is_new_user: bool, resolved: bool) -> str:
    """Return a user_sources touch_type for an ad/source start.

    Unresolved tokens never become trusted campaign attribution.
    """
    if resolved:
        return "first" if is_new_user else "revisit"
    return "organic" if is_new_user else "revisit"


def should_notify_new_user(*, is_new_user: bool) -> bool:
    return is_new_user


def requires_product_campaign_onboarding(
    *,
    profile_completed: bool,
    tracking_product_id: object | None,
    focus_product_id: object | None,
) -> bool:
    """Require qualification only for incomplete, product-scoped campaign visitors."""
    return not profile_completed and is_product_campaign_entry(
        tracking_product_id=tracking_product_id,
        focus_product_id=focus_product_id,
    )


def is_product_campaign_entry(
    *,
    tracking_product_id: object | None,
    focus_product_id: object | None,
) -> bool:
    return tracking_product_id is not None and focus_product_id is not None
