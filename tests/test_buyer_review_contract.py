from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_buyer_review_requires_paid_purchase_context() -> None:
    repo = (ROOT / "backend/repositories/storefront.py").read_text(encoding="utf-8")
    assert "o.status='paid'" in repo
    assert "one review per customer/product" in (ROOT / "database/migrations/0012_final_integration.sql").read_text(encoding="utf-8").lower()


def test_review_auto_publish_is_explicit_setting_not_default() -> None:
    migration = (ROOT / "database/migrations/0012_final_integration.sql").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/miniapp.py").read_text(encoding="utf-8")
    assert "('reviews.auto_publish','false'::jsonb" in migration
    assert "reviews.auto_publish" in service
    assert "verified_purchase" in service
