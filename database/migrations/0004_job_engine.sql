-- Zemen Digital S03 — durable PostgreSQL task engine.
-- PostgreSQL is the durable source of truth; LISTEN/NOTIFY is only a wake-up hint.

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS queue TEXT NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS trace_id UUID NOT NULL DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS first_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS error_code TEXT,
    ADD COLUMN IF NOT EXISTS result JSONB;

CREATE TABLE IF NOT EXISTS job_attempts (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    worker_id TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'running'
        CHECK (outcome IN ('running', 'completed', 'retry', 'failed', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    duration_ms BIGINT CHECK (duration_ms IS NULL OR duration_ms >= 0),
    error_code TEXT,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (job_id, attempt_no)
);

DROP INDEX IF EXISTS idx_jobs_due;
CREATE INDEX IF NOT EXISTS idx_jobs_due
    ON jobs (queue, priority, run_at, id)
    WHERE status = 'queued';

DROP INDEX IF EXISTS idx_jobs_stale;
CREATE INDEX IF NOT EXISTS idx_jobs_stale
    ON jobs (lease_expires_at, id)
    WHERE status = 'running';

CREATE INDEX IF NOT EXISTS idx_job_attempts_job
    ON job_attempts (job_id, attempt_no DESC);

CREATE INDEX IF NOT EXISTS idx_job_attempts_outcome
    ON job_attempts (outcome, started_at DESC);

CREATE OR REPLACE FUNCTION notify_zemen_job_queue()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'queued' THEN
        PERFORM pg_notify('zemen_jobs', NEW.id::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_zemen_job_queue ON jobs;
CREATE TRIGGER trg_notify_zemen_job_queue
AFTER INSERT OR UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION notify_zemen_job_queue();

COMMENT ON TABLE job_attempts IS
    'Execution history for the durable PostgreSQL job engine.';
COMMENT ON COLUMN jobs.lease_expires_at IS
    'If a worker dies, another worker may recover the job after this timestamp.';
COMMENT ON COLUMN jobs.job_key IS
    'Idempotency/dedupe key. Re-enqueueing the same key returns the existing job.';
