from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_pdf_media_is_browser_preview_friendly() -> None:
    source = (ROOT / "backend/api/routes/public_media.py").read_text(encoding="utf-8")

    assert '"Content-Disposition": f"inline;' in source
    assert '"Content-Length"' in source
    assert "quote(filename)" in source


def test_gallery_and_sample_events_do_not_use_unsupported_journey_weights() -> None:
    source = (ROOT / "backend/services/salesman.py").read_text(encoding="utf-8")
    method = source.split("async def record_media_action", 1)[1].split(
        "async def record_buy_click", 1
    )[0]

    assert '"GALLERY_OPENED"' in method
    assert '"SAMPLE_PDF_OPENED"' in method
    assert "record_unique_signal" not in method
    assert "self.events.append" in method
