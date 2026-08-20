import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDER_API = "https://zemen-digital-api.onrender.com/api/:path*"


def _vercel_config(app: str) -> dict[str, object]:
    return json.loads((ROOT / app / "vercel.json").read_text(encoding="utf-8"))


def test_frontends_build_as_independent_vite_projects() -> None:
    for app in ("miniapp", "dashboard"):
        config = _vercel_config(app)
        assert config["framework"] == "vite"
        assert config["buildCommand"] == "npm run build"
        assert config["outputDirectory"] == "dist"


def test_api_proxy_precedes_spa_fallback() -> None:
    for app in ("miniapp", "dashboard"):
        rewrites = _vercel_config(app)["rewrites"]
        assert isinstance(rewrites, list)
        assert rewrites[0] == {
            "source": "/api/:path*",
            "destination": RENDER_API,
        }
        assert rewrites[-1] == {
            "source": "/(.*)",
            "destination": "/index.html",
        }


def test_production_clients_use_same_origin_api_paths() -> None:
    miniapp_env = (ROOT / "miniapp/.env.production.example").read_text(encoding="utf-8")
    dashboard_env = (ROOT / "dashboard/.env.production.example").read_text(encoding="utf-8")
    dashboard_client = (ROOT / "dashboard/src/api/client.ts").read_text(encoding="utf-8")

    assert "VITE_API_BASE_URL=/api/miniapp" in miniapp_env
    assert "VITE_API_BASE=" in dashboard_env
    assert "credentials: 'include'" in dashboard_client
