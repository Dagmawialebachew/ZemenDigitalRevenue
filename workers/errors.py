from __future__ import annotations


class JobError(Exception):
    """Base error for durable-job execution."""

    code = "JOB_ERROR"


class RetryableJobError(JobError):
    code = "RETRYABLE"

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        if code:
            self.code = code


class PermanentJobError(JobError):
    code = "PERMANENT"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class JobLeaseLost(JobError):
    code = "LEASE_LOST"
