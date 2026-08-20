# Durable jobs — Section 03

Zemen does **not** use Redis.

> PostgreSQL remembers the work. asyncio performs the work.

A job is persisted before execution. Workers claim due rows using
`FOR UPDATE SKIP LOCKED`, write an execution attempt, and hold a time-bound lease.
Long jobs renew the lease. If the process dies, stale leases are safely recovered.

`LISTEN zemen_jobs` / `pg_notify()` wakes workers quickly, but correctness does not
depend on notifications: fallback polling still finds every due job.

## Built-in S03 job types

- `system.noop` — infrastructure smoke test.
- `telegram.ops.notify` — durable ZEMEN OPS text notification.

Later sections add delivery, broadcast, automation, discount, payment and
post-purchase handlers without replacing this engine.

## Idempotency

`job_key` is unique. Enqueueing the same key twice returns the existing job.
Side-effecting handlers must also enforce domain-level idempotency.

## Retry behavior

- Telegram `retry_after` is respected exactly.
- Transient failures use bounded exponential backoff with jitter.
- Permanent destination/payload errors fail immediately.
- Unexpected errors retry until `max_attempts`.
- Expired worker leases are requeued unless the final attempt was reached.

## Smoke test

```powershell
python scripts/enqueue_job.py --type system.noop --key smoke:s03:1
```

Then open `/health/jobs`.
