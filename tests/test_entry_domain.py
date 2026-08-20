from backend.domain.entry import should_notify_new_user, source_touch_type


def test_resolved_new_source_is_first_touch() -> None:
    assert source_touch_type(is_new_user=True, resolved=True) == "first"


def test_resolved_returning_source_is_revisit() -> None:
    assert source_touch_type(is_new_user=False, resolved=True) == "revisit"


def test_unresolved_token_never_becomes_trusted_first_touch() -> None:
    assert source_touch_type(is_new_user=True, resolved=False) == "organic"


def test_new_user_ops_notification_contract() -> None:
    assert should_notify_new_user(is_new_user=True) is True
    assert should_notify_new_user(is_new_user=False) is False
