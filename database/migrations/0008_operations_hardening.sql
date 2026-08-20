-- SECTION 08 — delivery + operations hardening.
-- Durable delivery attempts, operational alerts, support/Ops linkage, and indexes
-- used by the live control-room APIs.

ALTER TABLE entitlements
    ADD COLUMN delivery_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (delivery_attempt_count >= 0),
    ADD COLUMN last_delivery_attempt_at TIMESTAMPTZ,
    ADD COLUMN last_delivery_error TEXT;

CREATE TABLE delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    entitlement_id UUID NOT NULL REFERENCES entitlements(id) ON DELETE CASCADE,
    job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    status TEXT NOT NULL CHECK (status IN ('started', 'delivered', 'retrying', 'failed', 'deduped')),
    telegram_message_id BIGINT,
    error_code TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (entitlement_id, job_id, attempt_no)
);

CREATE INDEX idx_delivery_attempts_entitlement
    ON delivery_attempts (entitlement_id, started_at DESC);

CREATE INDEX idx_entitlements_delivery_queue
    ON entitlements (delivery_status, last_delivery_attempt_at)
    WHERE delivery_status IN ('pending', 'queued', 'failed');

CREATE TABLE operational_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_key TEXT NOT NULL UNIQUE,
    severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'critical')),
    alert_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    entity_type TEXT,
    entity_id TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'acknowledged', 'resolved')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ops_chat_id BIGINT,
    ops_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_operational_alerts_open
    ON operational_alerts (status, severity, created_at DESC);

CREATE TRIGGER trg_operational_alerts_updated_at BEFORE UPDATE ON operational_alerts
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();

CREATE TABLE support_ops_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id UUID NOT NULL REFERENCES support_cases(id) ON DELETE CASCADE,
    support_message_id BIGINT REFERENCES support_messages(id) ON DELETE SET NULL,
    ops_chat_id BIGINT NOT NULL,
    ops_thread_id BIGINT,
    ops_message_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ops_chat_id, ops_message_id)
);

CREATE INDEX idx_support_ops_messages_case
    ON support_ops_messages (case_id, created_at DESC);

-- One open/waiting support case per customer/product/order context avoids ticket spam.
CREATE UNIQUE INDEX uq_support_live_context
    ON support_cases (
        user_id,
        COALESCE(product_id, '00000000-0000-0000-0000-000000000000'::uuid),
        COALESCE(order_id, '00000000-0000-0000-0000-000000000000'::uuid)
    )
    WHERE status IN ('open', 'waiting_customer', 'waiting_admin');

CREATE INDEX idx_payments_review_age
    ON payments (status, updated_at)
    WHERE status IN ('pending_review', 'flagged');

COMMENT ON TABLE delivery_attempts IS
'Immutable operational history for every product-delivery attempt.';
COMMENT ON TABLE operational_alerts IS
'Deduplicated business/worker alerts surfaced in ZEMEN OPS and later the dashboard.';
COMMENT ON TABLE support_ops_messages IS
'Links customer support messages to their ZEMEN OPS cards for reply/resolve workflows.';
