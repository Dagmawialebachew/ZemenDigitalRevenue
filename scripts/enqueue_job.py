from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse
import asyncio
import json

from backend.core.config import get_settings
from backend.db.pool import Database
from backend.repositories.jobs import JobRepository
from workers.models import EnqueueJob


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    db = Database(settings.database_url, settings.db_min_pool_size, settings.db_max_pool_size)
    await db.connect()
    try:
        repo = JobRepository(db)
        job = await repo.enqueue(
            EnqueueJob(
                job_type=args.type,
                queue=args.queue,
                payload=json.loads(args.payload),
                job_key=args.key,
            )
        )
        print(f"queued job id={job.id} key={job.job_key} status={job.status}")
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue a Zemen durable job")
    parser.add_argument("--type", default="system.noop")
    parser.add_argument("--queue", default="default")
    parser.add_argument("--payload", default='{"echo":"hello from S03"}')
    parser.add_argument("--key", default=None)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
