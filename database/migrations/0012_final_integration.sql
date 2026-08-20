-- SECTION 12 — final analytics, financial controls, review moderation,
-- safe dashboard settings/admin controls, and security hardening indexes.

CREATE TABLE IF NOT EXISTS business_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_date DATE NOT NULL DEFAULT CURRENT_DATE,
    category TEXT NOT NULL CHECK (category IN ('ads','software','contractor','bank_fee','refund_cost','operations','other')),
    amount_br NUMERIC(12,2) NOT NULL CHECK (amount_br > 0),
    description TEXT NOT NULL CHECK (char_length(trim(description)) BETWEEN 1 AND 500),
    reference TEXT,
    created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_business_expenses_updated_at BEFORE UPDATE ON business_expenses
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();

ALTER TABLE reviews
    ADD COLUMN IF NOT EXISTS moderated_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS moderated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS verified_purchase BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'customer' CHECK (source IN ('customer','imported'));

-- A featured review must be approved. This prevents accidentally publishing a
-- pending/rejected review just because the feature flag was toggled.
ALTER TABLE reviews DROP CONSTRAINT IF EXISTS reviews_featured_requires_approved;
ALTER TABLE reviews ADD CONSTRAINT reviews_featured_requires_approved
    CHECK (featured IS FALSE OR status='approved');

-- Mark customer reviews as verified when they are tied to a paid order that
-- contains the reviewed product. This is derived by the database, not trusted
-- from client input.
CREATE OR REPLACE FUNCTION zemen_review_verified_purchase()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.order_id IS NOT NULL AND EXISTS (
        SELECT 1
          FROM orders o
          JOIN order_items oi ON oi.order_id=o.id
         WHERE o.id=NEW.order_id
           AND o.user_id=NEW.user_id
           AND oi.product_id=NEW.product_id
           AND o.status='paid'
    ) THEN
        NEW.verified_purchase := TRUE;
    ELSE
        NEW.verified_purchase := FALSE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_review_verified_purchase ON reviews;
CREATE TRIGGER trg_review_verified_purchase
BEFORE INSERT OR UPDATE OF order_id,user_id,product_id ON reviews
FOR EACH ROW EXECUTE FUNCTION zemen_review_verified_purchase();

-- Legacy rows without a paid order are not silently represented as verified
-- buyer reviews. Keep them available for moderation as imported proof.
UPDATE reviews SET source='imported' WHERE order_id IS NULL AND source='customer';

-- If legacy data contains more than one order-backed row per customer/product,
-- preserve the newest as the customer review and classify older rows as imported.
WITH ranked AS (
    SELECT id,row_number() OVER (PARTITION BY user_id,product_id ORDER BY updated_at DESC,created_at DESC,id DESC) AS rn
    FROM reviews WHERE source='customer'
)
UPDATE reviews r SET source='imported' FROM ranked x WHERE r.id=x.id AND x.rn>1;

-- Customer-facing review submission is one review per customer/product. If a
-- customer wants to change it, the same row is updated and returns to pending.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reviews_customer_product
    ON reviews(user_id, product_id)
    WHERE source='customer';

CREATE TABLE IF NOT EXISTS control_login_attempts (
    id BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT,
    fingerprint_hash TEXT NOT NULL,
    succeeded BOOLEAN NOT NULL DEFAULT FALSE,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_control_login_attempts_window
    ON control_login_attempts(fingerprint_hash, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_control_login_attempts_telegram
    ON control_login_attempts(telegram_id, attempted_at DESC);

-- Analytics indexes deliberately match the final dashboard query shapes.
CREATE INDEX IF NOT EXISTS idx_events_time_type_product
    ON events(occurred_at DESC, event_type, product_id, user_id);
CREATE INDEX IF NOT EXISTS idx_orders_paid_source_time
    ON orders(paid_at DESC, source_tracking_link_id, pricing_type)
    WHERE status='paid';
CREATE INDEX IF NOT EXISTS idx_orders_user_paid_time
    ON orders(user_id, paid_at DESC)
    WHERE status='paid';
CREATE INDEX IF NOT EXISTS idx_expenses_date
    ON business_expenses(expense_date DESC, category);
CREATE INDEX IF NOT EXISTS idx_reviews_control_queue
    ON reviews(status, featured, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_control
    ON audit_logs(created_at DESC, actor_admin_id, action);

-- Non-secret business settings that are safe to edit from the dashboard.
INSERT INTO settings(key,value,description)
VALUES
  ('business.display_name','"Zemen Digital"'::jsonb,'Public business display name'),
  ('business.default_currency','"ETB"'::jsonb,'Reporting currency'),
  ('business.timezone','"Africa/Addis_Ababa"'::jsonb,'Business reporting timezone'),
  ('referrals.minimum_payout_br','500'::jsonb,'Minimum manual referral payout threshold'),
  ('reviews.prompt_enabled','true'::jsonb,'Allow verified buyers to leave a product review'),
  ('reviews.auto_publish','false'::jsonb,'Keep new reviews pending until an admin approves them')
ON CONFLICT (key) DO NOTHING;

COMMENT ON TABLE business_expenses IS
    'Operator-recorded business cash expenses. Financial dashboard labels net figures as an operational cash view, not formal accounting profit.';
COMMENT ON TABLE control_login_attempts IS
    'Durable rate-limit evidence for Zemen Control login attempts; stores only a keyed fingerprint hash, never the access key.';
