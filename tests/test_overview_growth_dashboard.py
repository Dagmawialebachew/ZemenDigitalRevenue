from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_overview_query_has_lifetime_and_timezone_correct_growth_metrics() -> None:
    repository = (ROOT / "backend/repositories/control.py").read_text(encoding="utf-8")

    assert "revenue_lifetime_br" in repository
    assert "users_lifetime" in repository
    assert "Africa/Addis_Ababa" in repository
    assert "generate_series($1 - 1, 0, -1)" in repository
    assert "status<>'deleted'" in repository
    assert 'result["range_days"]' in repository


def test_overview_api_accepts_only_supported_chart_ranges() -> None:
    route = (ROOT / "backend/api/routes/control.py").read_text(encoding="utf-8")

    assert "Literal[7, 14, 30, 90]" in route


def test_overview_keeps_existing_cards_and_adds_lifetime_values() -> None:
    view = (ROOT / "dashboard/src/views/OverviewView.tsx").read_text(encoding="utf-8")

    assert 'eyebrow="Revenue"' in view
    assert 'eyebrow="New users"' in view
    assert "Lifetime revenue" in view
    assert "Lifetime users" in view
    assert 'eyebrow="30-day conversion"' in view
    assert 'eyebrow="Commission owed"' in view


def test_combined_chart_is_interactive_and_dependency_free() -> None:
    chart = (ROOT / "dashboard/src/components/RevenueGrowthChart.tsx").read_text(
        encoding="utf-8"
    )
    package = (ROOT / "dashboard/package.json").read_text(encoding="utf-8")

    assert "[7, 14, 30, 90]" in chart
    assert "revenue-bar" in chart
    assert "users-line" in chart
    assert "chart-tooltip" in chart
    assert "onPointerMove" in chart
    assert "ArrowLeft" in chart and "ArrowRight" in chart
    assert "aria-pressed" in chart
    assert "recharts" not in package
