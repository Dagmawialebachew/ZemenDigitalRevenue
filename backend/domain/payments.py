from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import secrets

from backend.domain.enums import PaymentMethod, PaymentRejectReason, PricingType
from backend.domain.money import br
from backend.domain.pricing import PricingDecision, decide_price


@dataclass(frozen=True, slots=True)
class CheckoutPrice:
    regular_price_br: Decimal
    final_price_br: Decimal
    discount_br: Decimal
    pricing_type: PricingType
    commissionable: bool


def choose_checkout_price(
    *,
    regular_price_br: Decimal | str | int | float,
    offer_price_br: Decimal | str | int | float | None,
) -> CheckoutPrice:
    if offer_price_br is None:
        decision = decide_price(
            regular_price_br=regular_price_br,
            pricing_type=PricingType.REGULAR,
        )
    else:
        decision = decide_price(
            regular_price_br=regular_price_br,
            final_price_br=offer_price_br,
            pricing_type=PricingType.RECOVERY,
        )
    return _checkout_price(decision)


def _checkout_price(decision: PricingDecision) -> CheckoutPrice:
    return CheckoutPrice(
        regular_price_br=decision.regular_price_br,
        final_price_br=decision.final_price_br,
        discount_br=decision.discount_br,
        pricing_type=decision.pricing_type,
        commissionable=decision.commissionable,
    )


def new_order_public_id() -> str:
    return f"ZD-{secrets.token_hex(5).upper()}"


def new_payment_public_id() -> str:
    return f"PAY-{secrets.token_hex(5).upper()}"


def normalize_payment_method(value: str) -> PaymentMethod:
    try:
        method = PaymentMethod(value.strip().lower())
    except ValueError as exc:
        raise ValueError("unsupported payment method") from exc
    if method not in {PaymentMethod.CBE, PaymentMethod.TELEBIRR, PaymentMethod.OTHER_MANUAL}:
        raise ValueError("manual checkout only supports configured manual payment methods")
    return method


def normalize_reject_reason(value: str) -> PaymentRejectReason:
    try:
        return PaymentRejectReason(value.strip().lower())
    except ValueError as exc:
        raise ValueError("unsupported rejection reason") from exc


def commission_amount(*, gross_br: Decimal | str | int | float, rate_percent: Decimal | str | int | float) -> Decimal:
    gross = br(gross_br)
    rate = br(rate_percent)
    if gross <= 0:
        raise ValueError("gross must be positive")
    if rate < 0 or rate > 100:
        raise ValueError("commission rate must be between 0 and 100")
    return br(gross * rate / Decimal("100"))
