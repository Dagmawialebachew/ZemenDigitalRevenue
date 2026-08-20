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
