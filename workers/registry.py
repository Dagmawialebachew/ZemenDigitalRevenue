from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias

from workers.errors import PermanentJobError

if TYPE_CHECKING:
    from workers.context import WorkerContext
    from workers.models import Job

JobResult: TypeAlias = dict[str, Any] | None
JobHandler: TypeAlias = Callable[["WorkerContext", "Job"], Awaitable[JobResult]]


class JobRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        normalized = job_type.strip()
        if not normalized:
            raise ValueError("job_type cannot be empty")
        if normalized in self._handlers:
            raise ValueError(f"handler already registered for {normalized}")
        self._handlers[normalized] = handler

    def handler(self, job_type: str) -> JobHandler:
        try:
            return self._handlers[job_type]
        except KeyError as exc:
            raise PermanentJobError(
                f"No job handler registered for {job_type}",
                code="UNKNOWN_JOB_TYPE",
            ) from exc

    @property
    def job_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))
