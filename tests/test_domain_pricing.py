from decimal import Decimal

import pytest

from backend.domain.enums import PricingType
from backend.domain.errors import InvalidPricing
from backend.domain.pricing import decide_price
from backend.domain.referrals import calculate_commission


def test_full_price_sale_is_commissionable() -> None:
    price = decide_price(regular_price_br="549")
    assert price.final_price_br == Decimal("549.00")
    assert price.discount_br == Decimal("0.00")
    assert price.commissionable is True
    assert calculate_commission(
        paid_amount_br=price.final_price_br,
        rate_percent="10",
        pricing_type=price.pricing_type,
        discount_br=price.discount_br,
    ) == Decimal("54.90")


def test_recovery_sale_never_gets_commission() -> None:
    price = decide_price(
        regular_price_br="549",
        final_price_br="299",
        pricing_type=PricingType.RECOVERY,
    )
    assert price.discount_br == Decimal("250.00")
    assert price.commissionable is False
    assert calculate_commission(
        paid_amount_br=price.final_price_br,
        rate_percent="10",
        pricing_type=price.pricing_type,
        discount_br=price.discount_br,
    ) == Decimal("0.00")


def test_regular_type_cannot_hide_discount() -> None:
    with pytest.raises(InvalidPricing):
        decide_price(
            regular_price_br="549",
            final_price_br="299",
            pricing_type=PricingType.REGULAR,
        )
