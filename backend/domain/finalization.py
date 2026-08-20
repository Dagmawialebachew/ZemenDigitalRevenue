from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

_ALLOWED_EXPENSE_CATEGORIES = {
    "ads",
    "software",
    "contractor",
    "bank_fee",
    "refund_cost",
    "operations",
    "other",
}
_ALLOWED_ADMIN_ROLES = {"owner", "admin", "operator", "viewer"}
_SAFE_DASHBOARD_SETTINGS = {
    "business.display_name",
    "business.default_currency",
    "business.timezone",
    "referrals.minimum_payout_br",
    "reviews.prompt_enabled",
    "reviews.auto_publish",
}


def normalize_expense_category(value: str) -> str:
    category = value.strip().lower()
    if category not in _ALLOWED_EXPENSE_CATEGORIES:
        raise ValueError("unsupported expense category")
    return category


def normalize_admin_role(value: str) -> str:
    role = value.strip().lower()
    if role not in _ALLOWED_ADMIN_ROLES:
        raise ValueError("unsupported admin role")
    return role


def is_safe_dashboard_setting(key: str) -> bool:
    return key.strip().lower() in _SAFE_DASHBOARD_SETTINGS


def normalize_dashboard_setting(key: str, value: object) -> object:
    clean = key.strip().lower()
    if clean not in _SAFE_DASHBOARD_SETTINGS:
        raise ValueError("this setting is not dashboard-editable")
    if clean == "business.display_name":
        text = str(value).strip()
        if not 1 <= len(text) <= 120:
            raise ValueError("business display name must be 1-120 characters")
        return text
    if clean == "business.default_currency":
        text = str(value).strip().upper()
        if len(text) != 3 or not text.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return text
    if clean == "business.timezone":
        text = str(value).strip()
        if not text or len(text) > 100 or "/" not in text:
            raise ValueError("timezone must be an IANA-style name")
        return text
    if clean == "referrals.minimum_payout_br":
        amount = money(value)
        if amount < 0 or amount > Decimal("1000000"):
            raise ValueError("minimum payout is outside the supported range")
        return amount
    if clean in {"reviews.prompt_enabled", "reviews.auto_publish"}:
        if not isinstance(value, bool):
            raise ValueError("review settings must be true or false")
        return value
    raise ValueError("this setting is not dashboard-editable")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class CashView:
    gross_revenue_br: Decimal
    refunds_br: Decimal
    recorded_expenses_br: Decimal
    paid_commissions_br: Decimal
    net_cash_br: Decimal


def cash_view(
    *,
    gross_revenue_br: Decimal | int | float | str,
    refunds_br: Decimal | int | float | str,
    recorded_expenses_br: Decimal | int | float | str,
    paid_commissions_br: Decimal | int | float | str,
) -> CashView:
    gross = money(gross_revenue_br)
    refunds = money(refunds_br)
    expenses = money(recorded_expenses_br)
    commissions = money(paid_commissions_br)
    return CashView(
        gross_revenue_br=gross,
        refunds_br=refunds,
        recorded_expenses_br=expenses,
        paid_commissions_br=commissions,
        net_cash_br=money(gross - refunds - expenses - commissions),
    )
