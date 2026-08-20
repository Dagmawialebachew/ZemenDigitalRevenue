from decimal import Decimal

import pytest

from backend.domain.marketing import (
    clean_automation_steps,
    clean_broadcast_content,
    normalize_audience,
    validate_destination_url,
)


def test_product_scoped_audiences_require_product() -> None:
    with pytest.raises(ValueError):
        normalize_audience({"kind": "high_intent"})
    audience = normalize_audience({"kind": "high_intent", "product_id": "abc", "minimum_intent_score": 12})
    assert audience.product_id == "abc"
    assert audience.minimum_intent_score == 12


def test_broadcast_content_tracks_safe_buttons() -> None:
    value = clean_broadcast_content({
        "text": "Hello",
        "buttons": [{"key": "buy", "text": "Buy", "url": "https://t.me/example"}],
    })
    assert value is not None
    assert value["buttons"] == [{"key": "buy", "text": "Buy", "url": "https://t.me/example"}]


def test_media_broadcast_caption_is_bounded_for_idempotent_single_send() -> None:
    with pytest.raises(ValueError, match="1024"):
        clean_broadcast_content({
            "text": "x" * 1025,
            "media": {"type": "photo", "file_id": "telegram-file"},
        })


def test_broadcast_destination_rejects_javascript() -> None:
    with pytest.raises(ValueError):
        validate_destination_url("javascript:alert(1)")


def test_recovery_offer_step_is_normalized() -> None:
    steps = clean_automation_steps([
        {"step_key": "wait", "step_type": "wait", "config": {"seconds": 60}},
        {"step_key": "offer", "step_type": "create_offer", "config": {"price_br": "299", "expires_after_seconds": 3600}},
    ])
    offer = steps[1]
    assert Decimal(offer["config"]["price_br"]) == Decimal("299.00")
    assert offer["config"]["expires_after_seconds"] == 3600
