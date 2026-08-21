from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_liveness_supports_get_and_head_without_touching_dependencies() -> None:
    source = (ROOT / "backend/api/routes/health.py").read_text(encoding="utf-8")
    assert '@router.get("/health/live")' in source
    assert '@router.head("/health/live", include_in_schema=False)' in source
    head_handler = source.split("async def live_head", 1)[1].split("@router", 1)[0]
    assert "request.app.state" not in head_handler
    assert "Response(status_code=200)" in head_handler
