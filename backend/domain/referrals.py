from __future__ import annotations

from decimal import Decimal

from backend.domain.enums import PricingType
from backend.domain.errors import CommissionNotAllowed
from backend.domain.money import br


def calculate_commission(
    *,
    paid_amount_br: Decimal | int | str | float,
    rate_percent: Decimal | int | str | float,
    pricing_type: PricingType,
    discount_br: Decimal | int | str | float = 0,
) -> Decimal:
    """Calculate a referral commission under Zemen's locked rule.

    Full-price sales may earn commission. Any discounted/recovery/manual-discount
    sale earns zero commission, even if referral attribution exists.
    """
    paid = br(paid_amount_br)
    rate = Decimal(str(rate_percent))
    discount = br(discount_br)

    if rate < 0 or rate > 100:
        raise ValueError("Commission rate must be between 0 and 100")
    if paid <= 0:
        raise ValueError("Paid amount must be greater than zero")

    if pricing_type != PricingType.REGULAR or discount > 0:
        return br(0)

    return br(paid * rate / Decimal("100"))


def require_commissionable(*, pricing_type: PricingType, discount_br: Decimal) -> None:
    if pricing_type != PricingType.REGULAR or br(discount_br) > 0:
        raise CommissionNotAllowed("Discounted orders never earn referral commission")
