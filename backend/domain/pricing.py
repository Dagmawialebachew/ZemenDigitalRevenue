from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.domain.enums import PricingType
from backend.domain.errors import InvalidPricing
from backend.domain.money import br


@dataclass(frozen=True, slots=True)
class PricingDecision:
    regular_price_br: Decimal
    final_price_br: Decimal
    discount_br: Decimal
    pricing_type: PricingType
    commissionable: bool


def decide_price(
    *,
    regular_price_br: Decimal | int | str | float,
    final_price_br: Decimal | int | str | float | None = None,
    pricing_type: PricingType = PricingType.REGULAR,
) -> PricingDecision:
    regular = br(regular_price_br)
    final = regular if final_price_br is None else br(final_price_br)

    if regular <= 0:
        raise InvalidPricing("Regular price must be greater than zero")
    if final <= 0:
        raise InvalidPricing("Final price must be greater than zero")
    if final > regular:
        raise InvalidPricing("Final price cannot exceed the regular price in this pricing model")

    discount = br(regular - final)

    if pricing_type == PricingType.REGULAR and discount != 0:
        raise InvalidPricing("Regular pricing cannot contain a discount")
    if pricing_type != PricingType.REGULAR and discount <= 0:
        raise InvalidPricing("Discount pricing must reduce the regular price")

    # Locked Zemen rule: any discounted sale is non-commissionable.
    commissionable = pricing_type == PricingType.REGULAR and discount == 0

    return PricingDecision(
        regular_price_br=regular,
        final_price_br=final,
        discount_br=discount,
        pricing_type=pricing_type,
        commissionable=commissionable,
    )
