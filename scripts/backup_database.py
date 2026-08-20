from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
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
    parser = argparse.ArgumentParser(description="Create a PostgreSQL custom-format backup for Zemen Digital.")
    parser.add_argument("--out", default="backups", help="Backup directory (default: backups)")
    args = parser.parse_args()
    if shutil.which("pg_dump") is None:
        raise SystemExit("pg_dump was not found on PATH")
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump = out / f"zemen_{stamp}.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--compress=9", "--no-owner", "--no-acl", "--file", str(dump), settings.database_url],
        check=True,
        env={**os.environ, "PGAPPNAME": "zemen-backup"},
    )
    digest = sha256(dump)
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "filename": dump.name,
        "sha256": digest,
        "format": "postgresql-custom",
    }
    meta = dump.with_suffix(".json")
    meta.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Backup: {dump}")
    print(f"SHA256: {digest}")
    print(f"Metadata: {meta}")


if __name__ == "__main__":
    main()
