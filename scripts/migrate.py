from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
import re

import asyncpg
import structlog

from backend.core.config import get_settings

log = structlog.get_logger(__name__)
MIGRATION_RE = re.compile(r"^(\d{4})_[A-Za-z0-9_-]+\.sql$")
ADVISORY_LOCK_ID = 847_205_419_2026


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    path: Path
    checksum: str


def discover_migrations(directory: Path) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_RE.match(path.name)
        if not match:
            continue
        raw = path.read_bytes()
        migrations.append(
            Migration(
                version=match.group(1),
                name=path.name,
                path=path,
                checksum=hashlib.sha256(raw).hexdigest(),
            )
        )

    versions = [m.version for m in migrations]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version detected")

    return migrations


def default_migrations_directory() -> Path:
    # scripts/migrate.py lives under <project>/scripts/.
    # The canonical SQL migration directory is <project>/database/migrations/.
    return Path(__file__).resolve().parents[1] / "database" / "migrations"


async def apply_migrations(
    dsn: str,
    directory: Path | None = None,
) -> list[str]:
    if not dsn:
        raise RuntimeError("DATABASE_URL is required to run migrations")

    migrations_dir = directory or default_migrations_directory()

    if not migrations_dir.exists():
        raise RuntimeError(
            f"Migration directory does not exist: {migrations_dir}"
        )

    migrations = discover_migrations(migrations_dir)

    if not migrations:
        raise RuntimeError(
            f"No migrations found in: {migrations_dir}"
        )

    conn = await asyncpg.connect(dsn)
    applied_now: list[str] = []

    try:
        await conn.execute(
            "SELECT pg_advisory_lock($1)",
            ADVISORY_LOCK_ID,
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _zemen_schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        existing_rows = await conn.fetch(
            """
            SELECT version, checksum
            FROM _zemen_schema_migrations
            ORDER BY version
            """
        )
        existing = {
            row["version"]: row["checksum"]
            for row in existing_rows
        }

        for migration in migrations:
            if migration.version in existing:
                if existing[migration.version] != migration.checksum:
                    raise RuntimeError(
                        f"Migration {migration.version} checksum changed "
                        "after being applied"
                    )
                continue

            sql = migration.path.read_text(encoding="utf-8")

            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    """
                    INSERT INTO _zemen_schema_migrations (
                        version,
                        name,
                        checksum
                    )
                    VALUES ($1, $2, $3)
                    """,
                    migration.version,
                    migration.name,
                    migration.checksum,
                )

            applied_now.append(migration.name)
            log.info(
                "migration_applied",
                migration=migration.name,
            )

    finally:
        try:
            await conn.execute(
                "SELECT pg_advisory_unlock($1)",
                ADVISORY_LOCK_ID,
            )
        except Exception:
            pass

        await conn.close()

    return applied_now


async def _main() -> None:
    settings = get_settings()
    applied = await apply_migrations(settings.database_url)

    if applied:
        print("Applied migrations:")
        for name in applied:
            print(f"  - {name}")
    else:
        print("Database is already up to date.")


if __name__ == "__main__":
    asyncio.run(_main())