from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    job_key: str | None
    job_type: str
    queue: str
    payload: dict[str, Any]
    status: str
    priority: int
    run_at: datetime
    attempts: int
    max_attempts: int
    locked_at: datetime | None = None
    locked_by: str | None = None
    lease_expires_at: datetime | None = None
    cancel_requested_at: datetime | None = None
    trace_id: str | None = None
    last_error: str | None = None
    error_code: str | None = None
    result: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def attempts_remaining(self) -> int:
        return max(0, self.max_attempts - self.attempts)

    @property
    def final_attempt(self) -> bool:
        return self.attempts >= self.max_attempts


@dataclass(frozen=True, slots=True)
class EnqueueJob:
    job_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    queue: str = "default"
    job_key: str | None = None
    priority: int = 100
    run_at: datetime | None = None
    max_attempts: int = 5
