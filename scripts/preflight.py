from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import asyncio
from pathlib import Path
import shutil
import sys

import asyncpg

from backend.core.config import get_settings
from database.migrate import discover_migrations

ROOT = Path(__file__).resolve().parents[1]


def _mask(value: str) -> str:
    return "configured" if value else "missing"


async def _database_checks(dsn: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    if not dsn:
        return ["DATABASE_URL is missing"], notes
    try:
        conn = await asyncpg.connect(dsn, timeout=10)
    except Exception as exc:
        return [f"database connection failed: {type(exc).__name__}: {exc}"], notes
    try:
        version = await conn.fetchval("SHOW server_version")
        notes.append(f"PostgreSQL {version}")
        exists = await conn.fetchval("SELECT to_regclass('_zemen_schema_migrations') IS NOT NULL")
        if not exists:
            errors.append("database migrations have not been initialized; run python scripts/migrate.py")
        else:
            rows = await conn.fetch("SELECT version,name,checksum FROM _zemen_schema_migrations ORDER BY version")
            applied = {str(r['version']): str(r['checksum']) for r in rows}
            migrations = discover_migrations(ROOT / "database" / "migrations")
            for migration in migrations:
                if migration.version not in applied:
                    errors.append(f"migration not applied: {migration.name}")
                elif applied[migration.version] != migration.checksum:
                    errors.append(f"migration checksum mismatch: {migration.name}")
            notes.append(f"schema migrations: {len(rows)}/{len(migrations)} applied")
        required = ["users", "products", "orders", "payments", "jobs", "events", "audit_logs"]
        missing = [name for name in required if not await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)]
        if missing:
            errors.append("missing core tables: " + ", ".join(missing))
    finally:
        await conn.close()
    return errors, notes


async def run(strict: bool) -> int:
    settings = get_settings()
    errors = list(settings.runtime_errors())
    warnings: list[str] = []
    notes: list[str] = []

    if settings.app_env.value == "production":
        if not settings.control_cookie_secure:
            errors.append("CONTROL_COOKIE_SECURE must be true in production")
        if not settings.static_apps_enabled:
            warnings.append("STATIC_APPS_ENABLED is false; /store and /control will not be served by FastAPI")
        if settings.control_owner_key and len(settings.control_owner_key) < 24:
            errors.append("CONTROL_OWNER_KEY should be at least 24 characters")
        if settings.control_session_secret and len(settings.control_session_secret) < 32:
            errors.append("CONTROL_SESSION_SECRET should be at least 32 characters")
        if settings.mini_app_session_secret and len(settings.mini_app_session_secret) < 32:
            errors.append("MINI_APP_SESSION_SECRET should be at least 32 characters")
        if settings.bot_mode.value == "polling":
            warnings.append("production is still in polling mode; webhook mode is recommended when a stable HTTPS origin exists")

    if settings.manual_payment_in_telegram_enabled:
        warnings.append(
            "manual ETB checkout inside Telegram is enabled; verify the deployment surface against Telegram digital-goods policy before launch"
        )

    if settings.static_apps_enabled:
        for rel in ("miniapp/dist/index.html", "dashboard/dist/index.html"):
            if not (ROOT / rel).exists():
                errors.append(f"static frontend build missing: {rel}")

    db_errors, db_notes = await _database_checks(settings.database_url)
    errors.extend(db_errors)
    notes.extend(db_notes)

    if shutil.which("pg_dump"):
        notes.append("pg_dump available")
    else:
        warnings.append("pg_dump not found; database backup script will not work on this host")

    print("ZEMEN DIGITAL — PRODUCTION PREFLIGHT")
    print("=" * 42)
    print(f"environment: {settings.app_env.value}")
    print(f"bot token: {_mask(settings.bot_token)}")
    print(f"database: {_mask(settings.database_url)}")
    print(f"control auth: {_mask(settings.control_owner_key)}")
    for note in notes:
        print(f"[OK] {note}")
    for warning in warnings:
        print(f"[WARN] {warning}")
    for error in errors:
        print(f"[ERROR] {error}")
    if errors:
        print(f"\nFAILED: {len(errors)} blocking issue(s).")
        return 1
    if strict and warnings:
        print(f"\nFAILED STRICT MODE: {len(warnings)} warning(s).")
        return 2
    print("\nPASS: configuration/database checks are ready for this stage.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Zemen configuration, build outputs and database schema.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.strict)))


if __name__ == "__main__":
    main()
