from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

BR = Decimal("0.01")


def as_decimal(value: Decimal | int | str | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def br(value: Decimal | int | str | float) -> Decimal:
    """Normalize Ethiopian-birr money values to two decimal places."""
    return as_decimal(value).quantize(BR, rounding=ROUND_HALF_UP)
