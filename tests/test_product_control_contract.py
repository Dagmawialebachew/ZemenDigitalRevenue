from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_product_control_migration_locks_full_price_only_commission():
    text = (ROOT / "database/migrations/0010_product_control.sql").read_text(encoding="utf-8")
    assert "products_commission_only_full_price_locked" in text
    assert "CHECK (commission_only_full_price IS TRUE)" in text
    assert "uq_product_active_delivery_file" in text
    assert "product_relationships" in text


def test_product_control_routes_cover_full_editor_surface():
    text = (ROOT / "backend/api/routes/product_control.py").read_text(encoding="utf-8")
    for fragment in (
        '@router.post("", status_code=status.HTTP_201_CREATED)',
        '@router.patch("/{product_id}")',
        '/translations/{language}',
        '/media/upload',
        '/files/upload',
        '/content/{language}/{block_key}/{audience_key}',
        '/relationships',
        '/publish',
        '/hide',
    ):
        assert fragment in text
    assert "require_control_session" in text


def test_dashboard_product_editor_has_all_locked_sections():
    text = (ROOT / "dashboard/src/views/ProductsView.tsx").read_text(encoding="utf-8")
    for label in (
        "Basics & Pricing", "Store · AM", "Store · EN", "Media", "Delivery", "Bot Salesman", "Upsells"
    ):
        assert label in text
    assert "Discounted orders can never create referral commission" in text
    assert "Upload to Telegram storage" in text


def test_telegram_backed_media_is_proxied_without_exposing_bot_token():
    route = (ROOT / "backend/api/routes/public_media.py").read_text(encoding="utf-8")
    mini = (ROOT / "backend/services/miniapp.py").read_text(encoding="utf-8")
    assert "/product-media/{media_id}" in route
    assert "await bot.download" in route
    assert "BOT_TOKEN" not in route
    assert "public_api_base_url" in mini


def test_s10_still_has_no_redis_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "redis" not in requirements
    assert "redis" not in pyproject
