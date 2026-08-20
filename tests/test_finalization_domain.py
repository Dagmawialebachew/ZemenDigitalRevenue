from decimal import Decimal

import pytest

from backend.domain.finalization import (
    cash_view,
    is_safe_dashboard_setting,
    normalize_admin_role,
    normalize_dashboard_setting,
    normalize_expense_category,
)


def test_cash_view_uses_operational_cash_formula() -> None:
    view = cash_view(
        gross_revenue_br="1000",
        refunds_br="100",
        recorded_expenses_br="200",
        paid_commissions_br="50",
    )
    assert view.net_cash_br == Decimal("650.00")


def test_expense_and_admin_values_are_allowlisted() -> None:
    assert normalize_expense_category(" Ads ") == "ads"
    assert normalize_admin_role("VIEWER") == "viewer"
    with pytest.raises(ValueError):
        normalize_expense_category("crypto")
    with pytest.raises(ValueError):
        normalize_admin_role("superuser")


def test_dashboard_settings_are_exact_allowlist_not_prefix_only() -> None:
    assert is_safe_dashboard_setting("business.display_name")
    assert not is_safe_dashboard_setting("business.secret_token")
    with pytest.raises(ValueError):
        normalize_dashboard_setting("business.secret_token", "oops")


def test_dashboard_setting_values_are_typed() -> None:
    assert normalize_dashboard_setting("business.default_currency", "etb") == "ETB"
    assert normalize_dashboard_setting("referrals.minimum_payout_br", "500") == Decimal("500.00")
    assert normalize_dashboard_setting("reviews.auto_publish", False) is False
    with pytest.raises(ValueError):
        normalize_dashboard_setting("reviews.auto_publish", "false")
