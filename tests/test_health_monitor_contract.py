from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_liveness_get_stays_dependency_free_and_head_warms_database() -> None:
    source = (ROOT / "backend/api/routes/health.py").read_text(encoding="utf-8")
    assert '@router.get("/health/live")' in source
    assert '@router.head("/health/live", include_in_schema=False)' in source
    get_handler = source.split("async def live()", 1)[1].split("@router", 1)[0]
    head_handler = source.split("async def live_head", 1)[1].split("@router", 1)[0]
    assert "request.app.state" not in get_handler
    assert "db.ping()" in head_handler
    assert "asyncio.wait_for" in head_handler
    assert "status_code=200" in head_handler
