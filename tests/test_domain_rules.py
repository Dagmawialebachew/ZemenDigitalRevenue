from decimal import Decimal


def test_discounted_order_is_not_commissionable_rule() -> None:
    list_price = Decimal("549.00")
    discounted = Decimal("299.00")
    discount_amount = list_price - discounted
    commissionable = discount_amount == 0
    assert discount_amount == Decimal("250.00")
    assert commissionable is False


def test_full_price_order_is_commissionable_rule() -> None:
    list_price = Decimal("549.00")
    amount_due = Decimal("549.00")
    assert list_price - amount_due == 0
    assert (list_price - amount_due == 0) is True
