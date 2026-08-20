from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import asyncpg

from backend.db.pool import Database
from workers.errors import JobLeaseLost
from workers.models import EnqueueJob, Job


def _json_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            return decoded
    raise TypeError(f"Expected JSON object, got {type(value).__name__}")


def _job(row: asyncpg.Record) -> Job:
    return Job(
        id=row["id"],
        job_key=row["job_key"],
        job_type=row["job_type"],
        queue=row["queue"],
        payload=_json_dict(row["payload"]),
        status=row["status"],
        priority=row["priority"],
        run_at=row["run_at"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        locked_at=row["locked_at"],
        locked_by=row["locked_by"],
        lease_expires_at=row["lease_expires_at"],
        cancel_requested_at=row["cancel_requested_at"],
        trace_id=str(row["trace_id"]) if row["trace_id"] else None,
        last_error=row["last_error"],
        error_code=row["error_code"],
        result=_json_dict(row["result"]) if row["result"] is not None else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class JobRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    @staticmethod
    def _validate_spec(spec: EnqueueJob) -> None:
        if not spec.job_type.strip():
            raise ValueError("job_type cannot be empty")
        if spec.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if not 0 <= spec.priority <= 32767:
            raise ValueError("priority must fit SMALLINT and be >= 0")

    async def enqueue_in_tx(self, conn: asyncpg.Connection, spec: EnqueueJob) -> Job:
        """Insert a durable job using the caller's transaction.

        Financial state changes use this outbox-style path so the business change
        and the follow-up Telegram work commit together.
        """
        self._validate_spec(spec)
        job_key = spec.job_key or f"{spec.job_type}:{uuid4().hex}"
        run_at = spec.run_at or datetime.now(UTC)
        payload = json.dumps(spec.payload, separators=(",", ":"), ensure_ascii=False)
        row = await conn.fetchrow(
            """
            INSERT INTO jobs (
                job_key, job_type, queue, payload, priority, run_at, max_attempts
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
            ON CONFLICT (job_key) DO NOTHING
            RETURNING *
            """,
            job_key,
            spec.job_type,
            spec.queue,
            payload,
            spec.priority,
            run_at,
            spec.max_attempts,
        )
        if row is None:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE job_key = $1", job_key)
            if row is None:
                raise RuntimeError("job dedupe lookup failed")
        return _job(row)

    async def enqueue(self, spec: EnqueueJob) -> Job:
        async with self.db.transaction() as conn:
            return await self.enqueue_in_tx(conn, spec)

    async def claim_one(
        self,
        *,
        worker_id: str,
        queues: tuple[str, ...],
        lease_seconds: int,
    ) -> Job | None:
        if not queues:
            return None
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                """
                WITH candidate AS (
                    SELECT id
                    FROM jobs
                    WHERE status = 'queued'
                      AND run_at <= now()
                      AND queue = ANY($1::text[])
                    ORDER BY priority ASC, run_at ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE jobs AS j
                SET status = 'running',
                    attempts = j.attempts + 1,
                    locked_at = now(),
                    locked_by = $2,
                    lease_expires_at = now() + make_interval(secs => $3),
                    first_started_at = COALESCE(j.first_started_at, now()),
                    last_started_at = now(),
                    updated_at = now()
                FROM candidate
                WHERE j.id = candidate.id
                RETURNING j.*
                """,
                list(queues),
                worker_id,
                lease_seconds,
            )
            if row is None:
                return None
            await conn.execute(
                """
                INSERT INTO job_attempts (job_id, attempt_no, worker_id, outcome)
                VALUES ($1, $2, $3, 'running')
                """,
                row["id"],
                row["attempts"],
                worker_id,
            )
        return _job(row)

    async def extend_lease(
        self,
        *,
        job_id: int,
        attempt: int,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        async with self.db.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE jobs
                SET lease_expires_at = now() + make_interval(secs => $4),
                    locked_at = now(),
                    updated_at = now()
                WHERE id = $1
                  AND attempts = $2
                  AND locked_by = $3
                  AND status = 'running'
                  AND cancel_requested_at IS NULL
                """,
                job_id,
                attempt,
                worker_id,
                lease_seconds,
            )
        return result.endswith("1")

    async def cancel_requested(self, *, job_id: int) -> bool:
        async with self.db.acquire() as conn:
            value = await conn.fetchval(
                "SELECT cancel_requested_at IS NOT NULL FROM jobs WHERE id = $1",
                job_id,
            )
        return bool(value)

    async def complete(
        self,
        *,
        job: Job,
        worker_id: str,
        result: dict[str, Any] | None,
    ) -> None:
        encoded = json.dumps(result or {}, separators=(",", ":"), ensure_ascii=False)
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                """
                UPDATE jobs
                SET status = 'completed',
                    result = $4::jsonb,
                    completed_at = now(),
                    locked_at = NULL,
                    locked_by = NULL,
                    lease_expires_at = NULL,
                    last_error = NULL,
                    error_code = NULL,
                    updated_at = now()
                WHERE id = $1 AND attempts = $2 AND locked_by = $3 AND status = 'running'
                RETURNING id
                """,
                job.id,
                job.attempts,
                worker_id,
                encoded,
            )
            if row is None:
                raise JobLeaseLost(f"lease lost while completing job {job.id}")
            await self._finish_attempt(conn, job=job, worker_id=worker_id, outcome="completed")

    async def retry(
        self,
        *,
        job: Job,
        worker_id: str,
        delay_seconds: float,
        error_code: str,
        error_message: str,
    ) -> None:
        run_at = datetime.now(UTC) + timedelta(seconds=max(0.0, delay_seconds))
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                """
                UPDATE jobs
                SET status = 'queued',
                    run_at = $4,
                    locked_at = NULL,
                    locked_by = NULL,
                    lease_expires_at = NULL,
                    last_error = $5,
                    error_code = $6,
                    updated_at = now()
                WHERE id = $1 AND attempts = $2 AND locked_by = $3 AND status = 'running'
                RETURNING id
                """,
                job.id,
                job.attempts,
                worker_id,
                run_at,
                error_message[:4000],
                error_code[:100],
            )
            if row is None:
                raise JobLeaseLost(f"lease lost while retrying job {job.id}")
            await self._finish_attempt(
                conn,
                job=job,
                worker_id=worker_id,
                outcome="retry",
                error_code=error_code,
                error_message=error_message,
            )

    async def fail(
        self,
        *,
        job: Job,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                """
                UPDATE jobs
                SET status = 'failed',
                    failed_at = now(),
                    locked_at = NULL,
                    locked_by = NULL,
                    lease_expires_at = NULL,
                    last_error = $4,
                    error_code = $5,
                    updated_at = now()
                WHERE id = $1 AND attempts = $2 AND locked_by = $3 AND status = 'running'
                RETURNING id
                """,
                job.id,
                job.attempts,
                worker_id,
                error_message[:4000],
                error_code[:100],
            )
            if row is None:
                raise JobLeaseLost(f"lease lost while failing job {job.id}")
            await self._finish_attempt(
                conn,
                job=job,
                worker_id=worker_id,
                outcome="failed",
                error_code=error_code,
                error_message=error_message,
            )

    async def request_cancel(self, *, job_id: int) -> str | None:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow("SELECT status FROM jobs WHERE id=$1 FOR UPDATE", job_id)
            if row is None:
                return None
            status = row["status"]
            if status == "queued":
                await conn.execute(
                    """
                    UPDATE jobs SET status='cancelled', cancel_requested_at=now(),
                        completed_at=now(), updated_at=now()
                    WHERE id=$1
                    """,
                    job_id,
                )
                return "cancelled"
            if status == "running":
                await conn.execute(
                    "UPDATE jobs SET cancel_requested_at=now(), updated_at=now() WHERE id=$1",
                    job_id,
                )
                return "cancellation_requested"
            return status

    async def mark_cancelled(self, *, job: Job, worker_id: str) -> None:
        async with self.db.transaction() as conn:
            row = await conn.fetchrow(
                """
                UPDATE jobs
                SET status='cancelled', completed_at=now(), locked_at=NULL,
                    locked_by=NULL, lease_expires_at=NULL, updated_at=now()
                WHERE id=$1 AND attempts=$2 AND locked_by=$3 AND status='running'
                RETURNING id
                """,
                job.id,
                job.attempts,
                worker_id,
            )
            if row is None:
                raise JobLeaseLost(f"lease lost while cancelling job {job.id}")
            await self._finish_attempt(conn, job=job, worker_id=worker_id, outcome="cancelled")

    async def recover_stale(self, *, limit: int = 100) -> tuple[int, int]:
        requeued = 0
        failed = 0
        async with self.db.transaction() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM jobs
                WHERE status='running' AND lease_expires_at IS NOT NULL AND lease_expires_at < now()
                ORDER BY lease_expires_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT $1
                """,
                limit,
            )
            for row in rows:
                attempt = int(row["attempts"])
                locked_by = row["locked_by"]
                if attempt >= int(row["max_attempts"]):
                    await conn.execute(
                        """
                        UPDATE jobs SET status='failed', failed_at=now(), locked_at=NULL,
                            locked_by=NULL, lease_expires_at=NULL,
                            error_code='LEASE_EXPIRED', last_error='Worker lease expired on final attempt',
                            updated_at=now()
                        WHERE id=$1
                        """,
                        row["id"],
                    )
                    outcome = "failed"
                    failed += 1
                else:
                    await conn.execute(
                        """
                        UPDATE jobs SET status='queued', run_at=now(), locked_at=NULL,
                            locked_by=NULL, lease_expires_at=NULL,
                            error_code='LEASE_EXPIRED', last_error='Worker lease expired; recovered',
                            updated_at=now()
                        WHERE id=$1
                        """,
                        row["id"],
                    )
                    outcome = "retry"
                    requeued += 1
                await conn.execute(
                    """
                    UPDATE job_attempts
                    SET outcome=$4, finished_at=now(), error_code='LEASE_EXPIRED',
                        error_message='Worker lease expired before completion'
                    WHERE job_id=$1 AND attempt_no=$2 AND worker_id=$3 AND outcome='running'
                    """,
                    row["id"],
                    attempt,
                    locked_by,
                    outcome,
                )
        return requeued, failed

    async def metrics(self) -> dict[str, int]:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    count(*) FILTER (WHERE status='queued' AND run_at <= now()) AS due,
                    count(*) FILTER (WHERE status='queued' AND run_at > now()) AS scheduled,
                    count(*) FILTER (WHERE status='running') AS running,
                    count(*) FILTER (WHERE status='running' AND lease_expires_at < now()) AS stale,
                    count(*) FILTER (WHERE status='failed') AS failed
                FROM jobs
                """
            )
        return {key: int(row[key] or 0) for key in ("due", "scheduled", "running", "stale", "failed")}

    @staticmethod
    async def _finish_attempt(
        conn: asyncpg.Connection,
        *,
        job: Job,
        worker_id: str,
        outcome: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await conn.execute(
            """
            UPDATE job_attempts
            SET outcome=$4, finished_at=now(),
                duration_ms=GREATEST(0, (EXTRACT(EPOCH FROM (now()-started_at))*1000)::bigint),
                error_code=$5, error_message=$6
            WHERE job_id=$1 AND attempt_no=$2 AND worker_id=$3 AND outcome='running'
            """,
            job.id,
            job.attempts,
            worker_id,
            outcome,
            error_code[:100] if error_code else None,
            error_message[:4000] if error_message else None,
        )
