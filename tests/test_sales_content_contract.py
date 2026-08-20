from pathlib import Path


def test_sales_content_is_dashboard_override_ready():
    repo = Path("backend/repositories/sales_content.py").read_text(encoding="utf-8")
    service = Path("backend/services/salesman.py").read_text(encoding="utf-8")
    assert "product_content_blocks" in repo
    assert "audience_key" in repo
    assert 'block_key="sales_hook"' in service
    assert 'block_key=f"sales_{kind}"' in service


def test_buy_click_is_recorded_not_paid():
    service = Path("backend/services/salesman.py").read_text(encoding="utf-8")
    router = Path("bot/routers/sales.py").read_text(encoding="utf-8")
    assert 'signal_key="BUY_CLICKED"' in service
    assert 'stage="buy_clicked"' in service
    assert "order paid" not in router.lower()
