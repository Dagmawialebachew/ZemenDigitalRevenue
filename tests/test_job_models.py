from __future__ import annotations

from datetime import UTC, datetime

from workers.models import Job


def make_job(attempts: int, max_attempts: int) -> Job:
    return Job(
        id=1,
        job_key="k",
        job_type="system.noop",
        queue="default",
        payload={},
        status="running",
        priority=100,
        run_at=datetime.now(UTC),
        attempts=attempts,
        max_attempts=max_attempts,
    )


def test_final_attempt_and_remaining() -> None:
    assert make_job(1, 5).attempts_remaining == 4
    assert make_job(1, 5).final_attempt is False
    assert make_job(5, 5).attempts_remaining == 0
    assert make_job(5, 5).final_attempt is True
