from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_free_backend_service_and_safe_health_check() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "runtime: docker" in blueprint
    assert "plan: free" in blueprint
    assert "dockerfilePath: ./Dockerfile.render" in blueprint
    assert "healthCheckPath: /health/live" in blueprint
    assert "maxShutdownDelaySeconds" not in blueprint
    assert 'key: STATIC_APPS_ENABLED\n        value: "false"' in blueprint


def test_render_blueprint_keeps_the_customer_database_path_warm() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert 'key: DB_MIN_POOL_SIZE\n        value: "1"' in blueprint
    assert 'key: DB_MAX_POOL_SIZE\n        value: "3"' in blueprint
    assert 'key: DB_MAX_INACTIVE_CONNECTION_LIFETIME_SECONDS\n        value: "600"' in blueprint
    assert 'key: WORKER_LISTEN_NOTIFY_ENABLED\n        value: "false"' in blueprint
    assert 'key: WORKER_POLL_FALLBACK_SECONDS\n        value: "900"' in blueprint
    assert 'key: WORKER_RECOVERY_INTERVAL_SECONDS\n        value: "900"' in blueprint


def test_telegram_webhook_secret_is_entered_with_valid_characters() -> None:
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "key: TELEGRAM_WEBHOOK_SECRET\n        sync: false" in blueprint
    assert "key: TELEGRAM_WEBHOOK_SECRET\n        generateValue: true" not in blueprint


def test_render_image_is_backend_only_and_does_not_copy_secrets() -> None:
    dockerfile = (ROOT / "Dockerfile.render").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "COPY backend ./backend" in dockerfile
    assert "COPY bot ./bot" in dockerfile
    assert "COPY workers ./workers" in dockerfile
    assert "COPY miniapp" not in dockerfile
    assert "COPY dashboard" not in dockerfile
    assert ".env" in dockerignore
    assert "*.env" in dockerignore
    assert "env" in dockerignore
    assert "env/" in gitignore


def test_production_startup_honors_render_port() -> None:
    startup = (ROOT / "scripts/start-production.sh").read_text(encoding="utf-8")

    assert 'APP_PORT="${PORT:-${APP_PORT:-8000}}"' in startup
    assert "export APP_PORT" in startup
    assert 'PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"' in startup
    assert 'PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"' in startup
    assert "export PYTHONPATH" in startup
    assert "python scripts/migrate.py" in startup
    assert "python scripts/preflight.py" in startup
    assert "exec python main.py" in startup
