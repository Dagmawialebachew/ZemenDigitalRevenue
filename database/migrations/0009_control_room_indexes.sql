-- SECTION 09 — Zemen Control query/index hardening.
-- No new business state is introduced here; these indexes make the control-room
-- read paths predictable as customers, events, orders, and support volume grow.

CREATE INDEX IF NOT EXISTS idx_orders_control_created
    ON orders (created_at DESC, status);

CREATE INDEX IF NOT EXISTS idx_orders_control_paid
    ON orders (paid_at DESC)
    WHERE status = 'paid';

CREATE INDEX IF NOT EXISTS idx_orders_user_recent
    ON orders (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_users_control_stage_seen
    ON users (customer_stage, last_seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_users_control_created
    ON users (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_control_time_type
    ON events (occurred_at DESC, event_type);

CREATE INDEX IF NOT EXISTS idx_events_control_user_time
    ON events (user_id, occurred_at DESC)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_support_cases_control_queue
    ON support_cases (status, priority, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_commissions_control_status
    ON commissions (status, created_at DESC);

COMMENT ON INDEX idx_orders_control_paid IS
'Fast recent-revenue and recent-sale reads for Zemen Control.';
