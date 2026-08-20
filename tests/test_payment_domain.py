from decimal import Decimal
import re

import pytest

from backend.domain.enums import PaymentMethod, PaymentRejectReason
from backend.domain.payments import (
    choose_checkout_price,
    commission_amount,
    new_order_public_id,
    new_payment_public_id,
    normalize_payment_method,
    normalize_reject_reason,
)


def test_regular_checkout_is_commissionable() -> None:
    price = choose_checkout_price(regular_price_br="549", offer_price_br=None)
    assert price.final_price_br == Decimal("549.00")
    assert price.discount_br == Decimal("0.00")
    assert price.commissionable is True
    assert commission_amount(gross_br=price.final_price_br, rate_percent="10") == Decimal("54.90")


def test_recovery_checkout_is_never_commissionable() -> None:
    price = choose_checkout_price(regular_price_br="549", offer_price_br="299")
    assert price.final_price_br == Decimal("299.00")
    assert price.discount_br == Decimal("250.00")
    assert price.commissionable is False


def test_public_payment_ids_are_short_telegram_safe_tokens() -> None:
    assert re.fullmatch(r"ZD-[A-F0-9]{10}", new_order_public_id())
    assert re.fullmatch(r"PAY-[A-F0-9]{10}", new_payment_public_id())


def test_manual_payment_method_normalization() -> None:
    assert normalize_payment_method("CBE") == PaymentMethod.CBE
    assert normalize_payment_method("telebirr") == PaymentMethod.TELEBIRR
    with pytest.raises(ValueError):
        normalize_payment_method("telegram_stars")


def test_rejection_reason_normalization() -> None:
    assert normalize_reject_reason("wrong_amount") == PaymentRejectReason.WRONG_AMOUNT
    assert normalize_reject_reason("OTHER") == PaymentRejectReason.OTHER
    with pytest.raises(ValueError):
        normalize_reject_reason("made_up_reason")
