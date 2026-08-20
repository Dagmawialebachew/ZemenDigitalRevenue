from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_miniapp_has_five_locked_tabs() -> None:
    text = (ROOT / "miniapp/src/components/BottomNav.tsx").read_text(encoding="utf-8")
    for key in ("home", "store", "library", "earn", "account"):
        assert f"'{key}'" in text


def test_zemen_palette_and_not_white_saas() -> None:
    css = (ROOT / "miniapp/src/styles.css").read_text(encoding="utf-8").lower()
    assert "--z-black: #050605" in css
    assert "--z-green: #8bdf31" in css
    assert "--z-ivory: #f3f0e7" in css
    assert "background: var(--z-black)" in css


def test_referral_full_price_rule_is_visible_to_customer() -> None:
    text = (ROOT / "miniapp/src/i18n/index.ts").read_text(encoding="utf-8")
    assert "Discounted sales earn no commission" in text
    assert "Discount ሽያጭ ኮሚሽን የለውም" in text


def test_miniapp_api_is_wired() -> None:
    router = (ROOT / "backend/api/router.py").read_text(encoding="utf-8")
    assert "miniapp_router" in router
    security = (ROOT / "backend/security/miniapp.py").read_text(encoding="utf-8")
    assert "WebAppData" in security
    assert "initDataUnsafe" in security
