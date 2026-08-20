from __future__ import annotations

from typing import Any

from workers.context import WorkerContext
from workers.models import Job


async def noop_handler(_ctx: WorkerContext, job: Job) -> dict[str, Any]:
    """Infrastructure smoke-test job. Safe to run in every environment."""
    return {"ok": True, "echo": job.payload.get("echo")}
