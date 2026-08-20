from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

from backend.core.config import get_settings


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a Zemen PostgreSQL custom-format backup.")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--sha256", help="Expected SHA-256 before restore")
    parser.add_argument("--confirm", help="Must be exactly RESTORE")
    args = parser.parse_args()
    if args.confirm != "RESTORE":
        raise SystemExit("Refusing destructive restore. Re-run with --confirm RESTORE")
    if shutil.which("pg_restore") is None:
        raise SystemExit("pg_restore was not found on PATH")
    path = args.backup.resolve()
    if not path.is_file():
        raise SystemExit(f"Backup does not exist: {path}")
    if args.sha256 and sha256(path).lower() != args.sha256.lower():
        raise SystemExit("Backup SHA-256 does not match")
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    print("WARNING: restoring with --clean --if-exists. Stop application writers first.")
    subprocess.run(
        ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", "--exit-on-error", "--dbname", settings.database_url, str(path)],
        check=True,
    )
    print("Restore complete. Run: python scripts/preflight.py")


if __name__ == "__main__":
    main()
