-- SECTION 11 — Marketing Engine
-- Broadcast Studio, durable retargeting automations, recovery offers,
-- referral payouts, ad-link management and attributable clicks.

ALTER TABLE broadcasts
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN IF NOT EXISTS audience_snapshot_count INTEGER NOT NULL DEFAULT 0 CHECK (audience_snapshot_count >= 0),
    ADD COLUMN IF NOT EXISTS send_mode TEXT NOT NULL DEFAULT 'telegram' CHECK (send_mode IN ('telegram')),
    ADD COLUMN IF NOT EXISTS attribution_window_hours INTEGER NOT NULL DEFAULT 168 CHECK (attribution_window_hours BETWEEN 1 AND 2160),
    ADD COLUMN IF NOT EXISTS cancel_requested_at TIMESTAMPTZ;

ALTER TABLE broadcast_recipients
    ADD COLUMN IF NOT EXISTS language TEXT CHECK (language IS NULL OR language IN ('am','en')),
    ADD COLUMN IF NOT EXISTS telegram_message_id BIGINT,
    ADD COLUMN IF NOT EXISTS last_job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE tracking_links
    ADD COLUMN IF NOT EXISTS label TEXT,
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN IF NOT EXISTS created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL;

ALTER TABLE discount_rules
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN IF NOT EXISTS created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS require_no_pending_payment BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS minimum_intent_score INTEGER NOT NULL DEFAULT 0 CHECK (minimum_intent_score BETWEEN 0 AND 1000);

ALTER TABLE automations
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS audience_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS trigger_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100 CHECK (priority BETWEEN 1 AND 1000),
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN IF NOT EXISTS created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL;

ALTER TABLE automation_steps
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE automation_runs
    ADD COLUMN IF NOT EXISTS trigger_event_id BIGINT REFERENCES events(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS stop_reason TEXT,
    ADD COLUMN IF NOT EXISTS last_step_started_at TIMESTAMPTZ;

ALTER TABLE customer_offers
    ADD COLUMN IF NOT EXISTS automation_run_id UUID REFERENCES automation_runs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS broadcast_click_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE CHECK (token ~ '^[A-Za-z0-9_-]{8,80}$'),
    broadcast_id UUID NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    button_key TEXT NOT NULL,
    destination_url TEXT NOT NULL,
    click_count INTEGER NOT NULL DEFAULT 0 CHECK (click_count >= 0),
    first_clicked_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    converted_order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broadcast_id, user_id, button_key)
);

CREATE TABLE IF NOT EXISTS referral_payout_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    payout_method TEXT NOT NULL CHECK (payout_method IN ('cbe','telebirr','other')),
    payout_destination TEXT NOT NULL,
    account_name TEXT,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_broadcasts_control_status_time
    ON broadcasts (status, scheduled_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_broadcast_recipients_status
    ON broadcast_recipients (broadcast_id, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_broadcast_click_user_time
    ON broadcast_click_links (user_id, clicked_at DESC) WHERE clicked_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tracking_links_control
    ON tracking_links (is_active, created_at DESC, product_id);
CREATE INDEX IF NOT EXISTS idx_discount_rules_control
    ON discount_rules (product_id, is_active, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_customer_offers_control
    ON customer_offers (status, starts_at, expires_at, product_id);
CREATE INDEX IF NOT EXISTS idx_automations_control
    ON automations (is_enabled, trigger_event, product_id, priority);
CREATE INDEX IF NOT EXISTS idx_automation_runs_trigger
    ON automation_runs (automation_id, trigger_event_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_run_event
    ON automation_runs (automation_id, user_id, trigger_event_id)
    WHERE trigger_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_commissions_available_queue
    ON commissions (status, available_at, referrer_user_id)
    WHERE status IN ('pending','available');
CREATE INDEX IF NOT EXISTS idx_payouts_control
    ON commission_payouts (status, created_at DESC);

-- Any event producer can trigger marketing automations without importing the
-- marketing service. The event is the durable boundary; a PostgreSQL job is the
-- durable execution signal. Matching/eligibility is rechecked by the worker.
CREATE OR REPLACE FUNCTION enqueue_marketing_automation_events()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO jobs (job_key, job_type, queue, payload, priority, run_at, max_attempts)
    SELECT
        'marketing:auto:trigger:' || a.id::text || ':event:' || NEW.id::text,
        'marketing.automation.trigger',
        'automation',
        jsonb_build_object('automation_id', a.id::text, 'event_id', NEW.id),
        LEAST(999, GREATEST(1, a.priority)),
        now(),
        8
    FROM automations a
    WHERE a.is_enabled = TRUE
      AND a.trigger_event = NEW.event_type
      AND (a.product_id IS NULL OR a.product_id = NEW.product_id)
    ON CONFLICT (job_key) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enqueue_marketing_automation_events ON events;
CREATE TRIGGER trg_enqueue_marketing_automation_events
AFTER INSERT ON events
FOR EACH ROW EXECUTE FUNCTION enqueue_marketing_automation_events();

-- The most recent broadcast click before a purchase receives last-click
-- attribution inside the broadcast's configured window. Acquisition source
-- attribution remains separate in tracking_links/user_sources.
CREATE OR REPLACE FUNCTION attribute_paid_order_to_broadcast()
RETURNS TRIGGER AS $$
DECLARE
    link_id UUID;
    b_id UUID;
BEGIN
    IF NEW.status <> 'paid' THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
            RETURN NEW;
        END IF;
    END IF;

    SELECT bcl.id, bcl.broadcast_id
          INTO link_id, b_id
        FROM broadcast_click_links bcl
        JOIN broadcasts b ON b.id=bcl.broadcast_id
        WHERE bcl.user_id=NEW.user_id
          AND bcl.clicked_at IS NOT NULL
          AND bcl.clicked_at <= COALESCE(NEW.paid_at, now())
          AND bcl.clicked_at >= COALESCE(NEW.paid_at, now()) - make_interval(hours => b.attribution_window_hours)
        ORDER BY bcl.clicked_at DESC
        LIMIT 1;

    IF link_id IS NOT NULL THEN
        UPDATE broadcast_click_links
           SET converted_order_id=COALESCE(converted_order_id, NEW.id), updated_at=now()
         WHERE id=link_id;
        UPDATE broadcast_recipients
           SET converted_order_id=COALESCE(converted_order_id, NEW.id), updated_at=now()
         WHERE broadcast_id=b_id AND user_id=NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_attribute_paid_order_to_broadcast ON orders;
CREATE TRIGGER trg_attribute_paid_order_to_broadcast
AFTER INSERT OR UPDATE OF status, paid_at ON orders
FOR EACH ROW EXECUTE FUNCTION attribute_paid_order_to_broadcast();

-- A purchase must kill any remaining recovery offer for the same product that
-- was not itself redeemed by the order. This prevents paid customers from
-- receiving a later recovery price because an old scheduled job wakes up.
CREATE OR REPLACE FUNCTION revoke_offers_after_purchase_event()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.event_type IN ('PAYMENT_APPROVED','PURCHASED')
       AND NEW.user_id IS NOT NULL AND NEW.product_id IS NOT NULL THEN
        UPDATE customer_offers
           SET status='revoked', updated_at=now()
         WHERE user_id=NEW.user_id
           AND product_id=NEW.product_id
           AND status IN ('scheduled','available')
           AND (NEW.order_id IS NULL OR id IS DISTINCT FROM (
               SELECT customer_offer_id FROM orders WHERE id=NEW.order_id
           ));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_revoke_offers_after_purchase_event ON events;
CREATE TRIGGER trg_revoke_offers_after_purchase_event
AFTER INSERT ON events
FOR EACH ROW EXECUTE FUNCTION revoke_offers_after_purchase_event();

COMMENT ON TABLE broadcast_click_links IS
    'Per-recipient tracked broadcast buttons. Tokens identify the recipient without exposing user IDs in the URL.';
COMMENT ON COLUMN automations.audience_definition IS
    'Dashboard-defined eligibility filter, re-evaluated when an event starts a run.';
COMMENT ON COLUMN discount_rules.require_no_pending_payment IS
    'Recovery rules must not undercut customers who already entered the payment flow.';
