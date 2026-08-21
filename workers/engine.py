from __future__ import annotations

import asyncio
import contextlib
import socket
from typing import Any
from uuid import uuid4

import structlog

from backend.core.config import Settings
from backend.db.pool import Database
from backend.repositories.jobs import JobRepository
from backend.services.error_reporting import ErrorReporter
from workers.backoff import retry_delay_seconds
from workers.context import WorkerContext
from workers.errors import JobLeaseLost, PermanentJobError, RetryableJobError
from workers.models import Job
from workers.registry import JobRegistry

log = structlog.get_logger(__name__)
JOB_NOTIFY_CHANNEL = "zemen_jobs"


class WorkerSupervisor:
    """PostgreSQL-backed durable worker supervisor."""

    def __init__(
        self,
        *,
        db: Database,
        settings: Settings,
        registry: JobRegistry,
        bot: Any,
        error_reporter: ErrorReporter | None = None,
    ) -> None:
        self.db = db
        self.settings = settings
        self.registry = registry
        self.bot = bot
        self.error_reporter = error_reporter
        self.jobs = JobRepository(db)
        self.stop_event = asyncio.Event()
        self.wake_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self.instance_id = f"{socket.gethostname()}-{uuid4().hex[:8]}"

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def wake(self) -> None:
        """Prompt workers after request-driven jobs commit without polling PostgreSQL."""
        if self.running:
            self.wake_event.set()

    async def start(self) -> None:
        if self.running:
            return
        self.stop_event.clear()
        self.wake_event.set()
        self._task = asyncio.create_task(self._run(), name="zemen-worker-supervisor")
        log.info(
            "worker_supervisor_started",
            instance_id=self.instance_id,
            workers=self.settings.worker_concurrency,
            queues=self.settings.worker_queues,
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self.stop_event.set()
        self.wake_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=self.settings.worker_shutdown_grace_seconds)
        except TimeoutError:
            log.warning("worker_shutdown_grace_exceeded", instance_id=self.instance_id)
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        finally:
            self._task = None

    async def _run(self) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                if self.settings.worker_listen_notify_enabled:
                    tg.create_task(self._notification_listener(), name="job-pg-listener")
                tg.create_task(self._stale_recovery_loop(), name="job-stale-recovery")
                for index in range(self.settings.worker_concurrency):
                    worker_id = f"{self.instance_id}:w{index + 1}"
                    tg.create_task(self._worker_loop(worker_id), name=f"job-worker-{index + 1}")
        except* asyncio.CancelledError:
            raise
        except* Exception as group:
            log.exception(
                "worker_supervisor_taskgroup_failed",
                errors=[str(error) for error in group.exceptions],
            )
            if self.error_reporter is not None:
                self.error_reporter.schedule(group, surface="worker_supervisor")

    async def _worker_loop(self, worker_id: str) -> None:
        ctx = WorkerContext(settings=self.settings, db=self.db, jobs=self.jobs, bot=self.bot)
        while not self.stop_event.is_set():
            try:
                job = await self.jobs.claim_one(
                    worker_id=worker_id,
                    queues=self.settings.worker_queues,
                    lease_seconds=self.settings.worker_lease_seconds,
                )
                if job is None:
                    await self._wait_for_work()
                    continue
                await self._execute(ctx, worker_id, job)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("worker_loop_error", worker_id=worker_id)
                if self.error_reporter is not None:
                    self.error_reporter.schedule(
                        exc,
                        surface="worker_loop",
                        context={"worker_id": worker_id},
                    )
                await self._sleep_or_stop(self.settings.worker_error_sleep_seconds)

    async def _execute(self, ctx: WorkerContext, worker_id: str, job: Job) -> None:
        log.info(
            "job_started",
            job_id=job.id,
            job_type=job.job_type,
            attempt=job.attempts,
            worker_id=worker_id,
            trace_id=job.trace_id,
        )

        if job.cancel_requested_at is not None or await self.jobs.cancel_requested(job_id=job.id):
            await self.jobs.mark_cancelled(job=job, worker_id=worker_id)
            log.info("job_cancelled_before_execution", job_id=job.id)
            return

        lease_stop = asyncio.Event()
        lease_task = asyncio.create_task(
            self._lease_heartbeat(job, worker_id, lease_stop),
            name=f"lease-{job.id}",
        )
        try:
            handler = self.registry.handler(job.job_type)
            result = await handler(ctx, job)
            if await self.jobs.cancel_requested(job_id=job.id):
                await self.jobs.mark_cancelled(job=job, worker_id=worker_id)
                log.info("job_cancelled_after_handler", job_id=job.id)
                return
            await self.jobs.complete(job=job, worker_id=worker_id, result=result)
            log.info("job_completed", job_id=job.id, attempt=job.attempts)
        except JobLeaseLost:
            log.warning("job_lease_lost", job_id=job.id, worker_id=worker_id)
        except PermanentJobError as exc:
            await self._terminal_failure(job, worker_id, exc.code, str(exc))
        except RetryableJobError as exc:
            await self._retry_or_fail(
                job,
                worker_id,
                error_code=exc.code,
                error_message=str(exc),
                explicit_delay=exc.retry_after,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("job_handler_unexpected_error", job_id=job.id, job_type=job.job_type)
            if self.error_reporter is not None:
                self.error_reporter.schedule(
                    exc,
                    surface="worker_job",
                    context={"job_id": job.id, "job_type": job.job_type},
                )
            await self._retry_or_fail(
                job,
                worker_id,
                error_code="UNHANDLED_EXCEPTION",
                error_message=f"{type(exc).__name__}: {exc}",
            )
        finally:
            lease_stop.set()
            lease_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await lease_task

    async def _retry_or_fail(
        self,
        job: Job,
        worker_id: str,
        *,
        error_code: str,
        error_message: str,
        explicit_delay: float | None = None,
    ) -> None:
        if job.final_attempt:
            await self._terminal_failure(job, worker_id, error_code, error_message)
            return
        delay = (
            explicit_delay
            if explicit_delay is not None
            else retry_delay_seconds(
                job.attempts,
                base_seconds=self.settings.worker_retry_base_seconds,
                cap_seconds=self.settings.worker_retry_cap_seconds,
            )
        )
        await self.jobs.retry(
            job=job,
            worker_id=worker_id,
            delay_seconds=delay,
            error_code=error_code,
            error_message=error_message,
        )
        self.wake_event.set()
        log.warning(
            "job_retry_scheduled",
            job_id=job.id,
            attempt=job.attempts,
            retry_in_seconds=round(delay, 2),
            error_code=error_code,
        )

    async def _terminal_failure(
        self,
        job: Job,
        worker_id: str,
        error_code: str,
        error_message: str,
    ) -> None:
        await self.jobs.fail(
            job=job,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
        )
        # Surface terminal failures in ZEMEN OPS without creating an alert loop.
        if self.settings.job_failure_alerts_enabled and job.job_type != "telegram.ops.alert":
            try:
                from backend.repositories.operations import OperationsRepository
                from workers.models import EnqueueJob

                async with self.db.transaction() as conn:
                    alert = await OperationsRepository().upsert_alert(
                        conn,
                        alert_key=f"job-failed:{job.id}",
                        severity="critical",
                        alert_type="job_terminal_failure",
                        title=f"Job failed · {job.job_type}",
                        body=f"{error_code}: {error_message}",
                        entity_type="job",
                        entity_id=str(job.id),
                        metadata={"attempt": job.attempts, "job_key": job.job_key},
                    )
                    await self.jobs.enqueue_in_tx(
                        conn,
                        EnqueueJob(
                            job_type="telegram.ops.alert",
                            queue="telegram",
                            job_key=f"ops-alert:{alert['id']}",
                            payload={"alert_id": str(alert["id"])},
                            priority=10,
                            max_attempts=5,
                        ),
                    )
            except Exception as exc:
                log.exception("job_failure_alert_enqueue_failed", job_id=job.id)
                if self.error_reporter is not None:
                    self.error_reporter.schedule(
                        exc,
                        surface="worker_alert",
                        context={"job_id": job.id, "job_type": job.job_type},
                    )
        log.error(
            "job_failed_terminally",
            job_id=job.id,
            job_type=job.job_type,
            attempt=job.attempts,
            error_code=error_code,
            error=error_message,
        )

    async def _lease_heartbeat(self, job: Job, worker_id: str, stop: asyncio.Event) -> None:
        interval = max(1.0, self.settings.worker_lease_seconds / 3)
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            ok = await self.jobs.extend_lease(
                job_id=job.id,
                attempt=job.attempts,
                worker_id=worker_id,
                lease_seconds=self.settings.worker_lease_seconds,
            )
            if not ok:
                log.warning("job_lease_heartbeat_lost", job_id=job.id, worker_id=worker_id)
                return

    async def _stale_recovery_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                requeued, failed = await self.jobs.recover_stale(
                    limit=self.settings.worker_recovery_batch_size
                )
                if requeued or failed:
                    self.wake_event.set()
                    log.warning("stale_jobs_recovered", requeued=requeued, failed=failed)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("stale_job_recovery_failed")
                if self.error_reporter is not None:
                    self.error_reporter.schedule(exc, surface="worker_recovery")
            await self._sleep_or_stop(self.settings.worker_recovery_interval_seconds)

    async def _notification_listener(self) -> None:
        pool = self.db.require_pool()
        while not self.stop_event.is_set():
            try:
                async with pool.acquire() as conn:

                    def on_notify(*_args: object) -> None:
                        self.wake_event.set()

                    await conn.add_listener(JOB_NOTIFY_CHANNEL, on_notify)
                    try:
                        while not self.stop_event.is_set():
                            await self._sleep_or_stop(30.0)
                    finally:
                        await conn.remove_listener(JOB_NOTIFY_CHANNEL, on_notify)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("job_notification_listener_failed")
                if self.error_reporter is not None:
                    self.error_reporter.schedule(exc, surface="worker_listener")
                await self._sleep_or_stop(self.settings.worker_error_sleep_seconds)

    async def _wait_for_work(self) -> None:
        self.wake_event.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                self.wake_event.wait(),
                timeout=self.settings.worker_poll_fallback_seconds,
            )

    async def _sleep_or_stop(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
