from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_control_room_stores_each_media_kind_natively() -> None:
    service = (ROOT / "backend/services/product_control.py").read_text(encoding="utf-8")
    assert "send_photo" in service
    assert "send_video" in service
    assert "send_document" in service
    assert 'mime_type == "application/pdf"' in service


def test_control_room_exposes_pdf_caption_and_order_controls() -> None:
    view = (ROOT / "dashboard/src/views/ProductsView.tsx").read_text(encoding="utf-8")
    assert "Free preview / PDF" in view
    assert "Bot caption" in view
    assert "Display order" in view
    assert 'application/pdf' in view


def test_bot_salesman_renders_control_room_media_with_fallbacks() -> None:
    router = (ROOT / "bot/routers/sales.py").read_text(encoding="utf-8")
    media = (ROOT / "bot/services/product_media.py").read_text(encoding="utf-8")
    assert '"sales:sample"' in router
    assert "send_sales_hero" in router
    assert "send_sales_gallery" in router
    assert "send_sample_pdf" in router
    assert "_fallback_source" in media


def test_storefront_preserves_complete_product_artwork() -> None:
    control_css = (ROOT / "dashboard/src/styles.css").read_text(encoding="utf-8")
    mini_css = (ROOT / "miniapp/src/styles.css").read_text(encoding="utf-8")
    assert ".product-control__cover img{width:100%;height:100%;object-fit:contain" in control_css
    assert ".product-cover img { width:100%; height:100%; object-fit:contain" in mini_css
    assert ".detail-media img,.detail-media video" in mini_css


def test_preview_pdf_never_uses_the_paid_delivery_file() -> None:
    media = (ROOT / "bot/services/product_media.py").read_text(encoding="utf-8")
    assert 'item.media_type == "preview"' in media
    assert "product_files" not in media
