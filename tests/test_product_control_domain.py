from decimal import Decimal

import pytest

from backend.domain.products import clean_faq, normalize_slug, readiness_report, validate_pricing


def test_product_slug_normalization_is_predictable():
    assert normalize_slug("  AI Kezero  ") == "ai-kezero"
    assert normalize_slug("AI__Kezero") == "ai-kezero"
    with pytest.raises(ValueError):
        normalize_slug("AI/kezero")


def test_recovery_price_must_be_lower_than_regular_price():
    regular, recovery = validate_pricing(regular_price_br="549", recovery_price_br="299")
    assert regular == Decimal("549.00")
    assert recovery == Decimal("299.00")
    with pytest.raises(ValueError):
        validate_pricing(regular_price_br=549, recovery_price_br=549)


def test_faq_parser_contract_filters_invalid_rows():
    result = clean_faq([
        {"question": "Who is this for?", "answer": "Beginners."},
        {"question": "", "answer": "ignored"},
        "not a mapping",
    ])
    assert result == [{"question": "Who is this for?", "answer": "Beginners."}]


def test_readiness_blocks_publish_without_delivery_for_digital_file():
    product = {
        "default_language": "am", "product_type": "digital_file", "category": "AI",
        "discounts_enabled": True, "recovery_price_br": Decimal("299"),
        "commission_only_full_price": True,
    }
    translations = [{"language": "am", "title": "AI ከዜሮ"}]
    media = [{"media_type": "cover", "is_active": True}]
    result = readiness_report(product=product, translations=translations, media=media, files=[])
    assert result["ready"] is False
    assert any("delivery file" in x.lower() for x in result["blockers"])


def test_readiness_allows_complete_digital_product():
    product = {
        "default_language": "am", "product_type": "digital_file", "category": "AI",
        "discounts_enabled": True, "recovery_price_br": Decimal("299"),
        "commission_only_full_price": True,
    }
    translations = [{"language": "am", "title": "AI ከዜሮ"}]
    media = [{"media_type": "cover", "is_active": True}]
    files = [{"is_active": True}]
    result = readiness_report(product=product, translations=translations, media=media, files=files)
    assert result["ready"] is True
    assert result["checks"]["commission_only_full_price"] is True
