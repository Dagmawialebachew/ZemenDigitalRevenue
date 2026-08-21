from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

log = structlog.get_logger(__name__)
_tasks: set[asyncio.Task[Any]] = set()


def run_background(coro: Coroutine[Any, Any, Any], *, name: str) -> None:
    """Run non-critical telemetry after the buyer-facing response is sent."""
    task = asyncio.create_task(coro, name=name)
    _tasks.add(task)

    def finished(completed: asyncio.Task[Any]) -> None:
        _tasks.discard(completed)
        try:
            completed.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            log.warning("background_telemetry_failed", task=name, error=str(exc))

    task.add_done_callback(finished)
