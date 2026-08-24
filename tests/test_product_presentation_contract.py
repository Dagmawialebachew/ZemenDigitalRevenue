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


def test_miniapp_explains_the_telegram_payment_handoff() -> None:
    app = (ROOT / "miniapp/src/App.tsx").read_text(encoding="utf-8")
    view = (ROOT / "miniapp/src/views/ProductView.tsx").read_text(encoding="utf-8")
    copy = (ROOT / "miniapp/src/i18n/index.ts").read_text(encoding="utf-8")
    assert "showPopup" not in app
    assert "payment-handoff" in view
    assert "Close this Mini App, return to Telegram" in copy
    assert "ይህን Mini App ይዝጉ" in copy
    assert "CBE or Telebirr" in copy
    assert "onOpenPayment" not in view
    assert "ክፍያውን በZemen bot ይክፈቱ" not in copy


def test_miniapp_uses_a_visible_gallery_and_readable_description() -> None:
    view = (ROOT / "miniapp/src/views/ProductView.tsx").read_text(encoding="utf-8")
    assert "descriptionParagraphs" in view
    assert "media-rail" in view
    assert "media-counter" in view


def test_social_proof_keeps_counts_without_short_testimonials() -> None:
    view = (ROOT / "miniapp/src/views/ProductView.tsx").read_text(encoding="utf-8")
    bot_copy = (ROOT / "bot/services/sales_copy.py").read_text(encoding="utf-8")

    assert "social-proof" in view
    assert "social_proof_text" in bot_copy
    assert "testimonial-strip" not in view
    assert "product.testimonials" not in view
    assert "Reader feedback" not in bot_copy
    assert "@Ber***sg" not in bot_copy


def test_sample_pdf_uses_telegram_external_link_handling() -> None:
    app = (ROOT / "miniapp/src/App.tsx").read_text(encoding="utf-8")
    view = (ROOT / "miniapp/src/views/ProductView.tsx").read_text(encoding="utf-8")
    webapp = (ROOT / "miniapp/src/telegram/webapp.ts").read_text(encoding="utf-8")

    assert "onOpenSample={openExternal}" in app
    assert "event.preventDefault()" in view
    assert "onOpenSample(samplePdf.url)" in view
    assert "ሳምፕ ፕሪቪው" in view
    assert "tg.openLink(url)" in webapp
