CREATE OR REPLACE FUNCTION zemen_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_user_profiles_updated_at BEFORE UPDATE ON user_profiles
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_products_updated_at BEFORE UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_product_translations_updated_at BEFORE UPDATE ON product_translations
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_product_content_blocks_updated_at BEFORE UPDATE ON product_content_blocks
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_discount_rules_updated_at BEFORE UPDATE ON discount_rules
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_customer_offers_updated_at BEFORE UPDATE ON customer_offers
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON orders
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON payments
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_commissions_updated_at BEFORE UPDATE ON commissions
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_commission_payouts_updated_at BEFORE UPDATE ON commission_payouts
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_broadcasts_updated_at BEFORE UPDATE ON broadcasts
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_automations_updated_at BEFORE UPDATE ON automations
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_automation_runs_updated_at BEFORE UPDATE ON automation_runs
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_jobs_updated_at BEFORE UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_reviews_updated_at BEFORE UPDATE ON reviews
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();
CREATE TRIGGER trg_support_cases_updated_at BEFORE UPDATE ON support_cases
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();

CREATE UNIQUE INDEX uq_user_sources_first_touch
ON user_sources (user_id)
WHERE touch_type = 'first';

CREATE INDEX idx_users_stage ON users (customer_stage, last_seen_at DESC);
CREATE INDEX idx_products_status_sort ON products (status, featured DESC, sort_order, created_at DESC);
CREATE INDEX idx_tracking_links_product ON tracking_links (product_id, is_active);
CREATE INDEX idx_user_sources_user_created ON user_sources (user_id, created_at DESC);
CREATE INDEX idx_referral_attributions_referrer ON referral_attributions (referrer_user_id, created_at DESC);
CREATE INDEX idx_orders_user_created ON orders (user_id, created_at DESC);
CREATE INDEX idx_orders_status_created ON orders (status, created_at DESC);
CREATE INDEX idx_orders_source ON orders (source_tracking_link_id, created_at DESC);
CREATE INDEX idx_payments_status_created ON payments (status, created_at DESC);
CREATE INDEX idx_payments_order ON payments (order_id, created_at DESC);
CREATE INDEX idx_payment_proofs_payment ON payment_proofs (payment_id, created_at DESC);
CREATE INDEX idx_entitlements_user ON entitlements (user_id, granted_at DESC);
CREATE INDEX idx_offers_user_product_status ON customer_offers (user_id, product_id, status, expires_at);
CREATE INDEX idx_commissions_referrer_status ON commissions (referrer_user_id, status, created_at DESC);
CREATE INDEX idx_events_type_time ON events (event_type, occurred_at DESC);
CREATE INDEX idx_events_user_time ON events (user_id, occurred_at DESC);
CREATE INDEX idx_events_product_time ON events (product_id, occurred_at DESC);
CREATE INDEX idx_automation_runs_due ON automation_runs (next_run_at, status) WHERE status IN ('active', 'waiting');
CREATE INDEX idx_jobs_due ON jobs (priority, run_at, id) WHERE status = 'queued';
CREATE INDEX idx_jobs_stale ON jobs (locked_at) WHERE status = 'running';
CREATE INDEX idx_reviews_product_status ON reviews (product_id, status, featured, created_at DESC);
CREATE INDEX idx_support_cases_status ON support_cases (status, priority, updated_at DESC);
CREATE INDEX idx_support_messages_case ON support_messages (case_id, created_at);
CREATE UNIQUE INDEX uq_active_customer_offer ON customer_offers (user_id, product_id) WHERE status IN ('scheduled', 'available');
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id, created_at DESC);

CREATE OR REPLACE FUNCTION enforce_commission_eligibility()
RETURNS TRIGGER AS $$
DECLARE
    order_row orders%ROWTYPE;
    item_row order_items%ROWTYPE;
    attribution_row referral_attributions%ROWTYPE;
    expected_gross NUMERIC(12,2);
    expected_amount NUMERIC(12,2);
BEGIN
    SELECT * INTO order_row FROM orders WHERE id = NEW.order_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Commission order does not exist';
    END IF;

    SELECT * INTO item_row FROM order_items WHERE id = NEW.order_item_id;
    IF NOT FOUND OR item_row.order_id <> NEW.order_id THEN
        RAISE EXCEPTION 'Commission order item does not belong to the order';
    END IF;

    SELECT * INTO attribution_row
    FROM referral_attributions
    WHERE id = NEW.referral_attribution_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Commission referral attribution does not exist';
    END IF;

    IF order_row.status <> 'paid' THEN
        RAISE EXCEPTION 'Commission can only be created for a paid order';
    END IF;

    -- LOCKED ZEMEN BUSINESS RULE:
    -- Discounted orders cannot generate referral commission.
    IF order_row.discount_total_br > 0 OR order_row.pricing_type <> 'regular' THEN
        RAISE EXCEPTION 'Discounted orders cannot generate referral commission';
    END IF;

    IF item_row.commissionable IS NOT TRUE OR item_row.discount_per_unit_br > 0 THEN
        RAISE EXCEPTION 'Order item is not commissionable';
    END IF;

    IF item_row.product_id <> NEW.product_id THEN
        RAISE EXCEPTION 'Commission product does not match order item';
    END IF;

    IF attribution_row.referrer_user_id <> NEW.referrer_user_id
       OR attribution_row.referred_user_id <> NEW.buyer_user_id THEN
        RAISE EXCEPTION 'Commission parties do not match referral attribution';
    END IF;

    IF order_row.referral_attribution_id IS DISTINCT FROM NEW.referral_attribution_id THEN
        RAISE EXCEPTION 'Order is not tied to this referral attribution';
    END IF;

    IF NEW.referrer_user_id = NEW.buyer_user_id THEN
        RAISE EXCEPTION 'Self-referral commission is not allowed';
    END IF;

    IF NEW.rate_percent <> item_row.referral_rate_percent_snapshot THEN
        RAISE EXCEPTION 'Commission rate must match order-time snapshot';
    END IF;

    expected_gross := round((item_row.unit_price_br * item_row.quantity)::numeric, 2);
    IF NEW.gross_paid_br <> expected_gross THEN
        RAISE EXCEPTION 'Commission gross amount must equal full-price order item total';
    END IF;

    expected_amount := round((NEW.gross_paid_br * NEW.rate_percent / 100.0)::numeric, 2);
    IF NEW.amount_br <> expected_amount THEN
        RAISE EXCEPTION 'Commission amount does not match gross x rate';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_commission_eligibility
BEFORE INSERT OR UPDATE ON commissions
FOR EACH ROW EXECUTE FUNCTION enforce_commission_eligibility();

CREATE OR REPLACE FUNCTION prevent_referral_self_attribution()
RETURNS TRIGGER AS $$
DECLARE
    account_owner UUID;
BEGIN
    IF NEW.referrer_user_id = NEW.referred_user_id THEN
        RAISE EXCEPTION 'Self referral is not allowed';
    END IF;

    SELECT owner_user_id INTO account_owner
    FROM referral_accounts
    WHERE id = NEW.referral_account_id;

    IF account_owner IS DISTINCT FROM NEW.referrer_user_id THEN
        RAISE EXCEPTION 'Referral account does not belong to referrer';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_referral_no_self
BEFORE INSERT OR UPDATE ON referral_attributions
FOR EACH ROW EXECUTE FUNCTION prevent_referral_self_attribution();

CREATE VIEW v_product_sales_summary AS
SELECT
    p.id AS product_id,
    p.slug,
    COUNT(DISTINCT o.id) FILTER (WHERE o.status = 'paid') AS paid_orders,
    COALESCE(SUM((oi.unit_price_br * oi.quantity)) FILTER (WHERE o.status = 'paid'), 0)::numeric(14,2) AS revenue_br,
    COUNT(DISTINCT o.id) FILTER (WHERE o.status = 'paid' AND oi.discount_per_unit_br = 0) AS full_price_orders,
    COUNT(DISTINCT o.id) FILTER (WHERE o.status = 'paid' AND oi.discount_per_unit_br > 0) AS discounted_orders
FROM products p
LEFT JOIN order_items oi ON oi.product_id = p.id
LEFT JOIN orders o ON o.id = oi.order_id
GROUP BY p.id, p.slug;
