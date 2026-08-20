-- SECTION 07 — manual payment/order review infrastructure.
-- This migration deliberately keeps order/payment state durable in PostgreSQL.

ALTER TABLE payment_proofs
    ADD COLUMN telegram_media_type TEXT NOT NULL DEFAULT 'photo'
        CHECK (telegram_media_type IN ('photo', 'document'));

ALTER TABLE payments
    ADD COLUMN public_id TEXT,
    ADD COLUMN latest_proof_id UUID REFERENCES payment_proofs(id) ON DELETE SET NULL;

UPDATE payments
SET public_id = 'PAY-' || upper(substr(replace(id::text, '-', ''), 1, 10))
WHERE public_id IS NULL;

ALTER TABLE payments
    ALTER COLUMN public_id SET NOT NULL;

CREATE UNIQUE INDEX uq_payments_public_id ON payments (public_id);

ALTER TABLE conversation_sessions
    ADD COLUMN active_order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    ADD COLUMN active_payment_id UUID REFERENCES payments(id) ON DELETE SET NULL;

CREATE INDEX idx_conversation_sessions_active_order
    ON conversation_sessions (active_order_id)
    WHERE active_order_id IS NOT NULL;

CREATE INDEX idx_conversation_sessions_active_payment
    ON conversation_sessions (active_payment_id)
    WHERE active_payment_id IS NOT NULL;

-- Only one live payment attempt per order at a time. Rejected payments are kept
-- and can accept a replacement proof rather than creating payment spam.
CREATE UNIQUE INDEX uq_live_payment_per_order
    ON payments (order_id)
    WHERE status IN ('awaiting_proof', 'pending_review', 'flagged', 'rejected');

-- Telegram file_unique_id is not a cryptographic receipt hash, but it is a useful
-- first duplicate signal. Keep the index non-unique so reviewers can see reuse
-- rather than losing forensic history.
CREATE INDEX idx_payment_proofs_unique_file
    ON payment_proofs (telegram_file_unique_id)
    WHERE telegram_file_unique_id IS NOT NULL;

CREATE TABLE payment_review_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    proof_id UUID NOT NULL REFERENCES payment_proofs(id) ON DELETE CASCADE,
    ops_chat_id BIGINT NOT NULL,
    ops_thread_id BIGINT,
    ops_message_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'approved', 'rejected', 'flagged', 'superseded')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ops_chat_id, ops_message_id)
);

CREATE INDEX idx_payment_review_messages_payment
    ON payment_review_messages (payment_id, created_at DESC);

CREATE TRIGGER trg_payment_review_messages_updated_at BEFORE UPDATE ON payment_review_messages
FOR EACH ROW EXECUTE FUNCTION zemen_set_updated_at();

-- The newest proof is always explicit on the payment row. This avoids races where
-- an admin reviews an older screenshot after the buyer has submitted a replacement.
CREATE OR REPLACE FUNCTION zemen_set_latest_payment_proof()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE payments
    SET latest_proof_id = NEW.id,
        updated_at = now()
    WHERE id = NEW.payment_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_proof_latest
AFTER INSERT ON payment_proofs
FOR EACH ROW EXECUTE FUNCTION zemen_set_latest_payment_proof();

-- Do not allow a payment to be approved for an amount different from the order's
-- final amount. This catches accidental admin/backend mistakes before money state
-- is finalized.
CREATE OR REPLACE FUNCTION enforce_payment_expected_amount()
RETURNS TRIGGER AS $$
DECLARE
    due NUMERIC(12,2);
BEGIN
    SELECT total_due_br INTO due FROM orders WHERE id = NEW.order_id;
    IF due IS NULL THEN
        RAISE EXCEPTION 'Payment order does not exist';
    END IF;
    IF NEW.expected_amount_br <> due THEN
        RAISE EXCEPTION 'Payment expected amount must equal order total_due_br';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_payment_expected_amount
BEFORE INSERT OR UPDATE OF expected_amount_br, order_id ON payments
FOR EACH ROW EXECUTE FUNCTION enforce_payment_expected_amount();

COMMENT ON TABLE payment_review_messages IS
'Links each Telegram ZEMEN OPS review card to the exact payment proof it displays.';
