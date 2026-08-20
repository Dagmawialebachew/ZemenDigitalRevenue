CREATE TABLE user_product_journeys (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    stage TEXT NOT NULL DEFAULT 'introduced' CHECK (stage IN (
        'introduced', 'exploring', 'interested', 'high_intent',
        'buy_clicked', 'awaiting_payment', 'customer'
    )),
    intent_score SMALLINT NOT NULL DEFAULT 0 CHECK (intent_score BETWEEN 0 AND 100),
    last_signal_key TEXT,
    onboarding_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    buy_clicked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, product_id)
);

CREATE TABLE user_product_signals (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    signal_key TEXT NOT NULL,
    score_delta SMALLINT NOT NULL DEFAULT 0 CHECK (score_delta BETWEEN -100 AND 100),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, product_id, signal_key)
);

CREATE INDEX idx_user_product_journeys_product_stage
    ON user_product_journeys (product_id, stage, intent_score DESC, last_seen_at DESC);

CREATE INDEX idx_user_product_journeys_user_seen
    ON user_product_journeys (user_id, last_seen_at DESC);

CREATE INDEX idx_user_product_signals_user_product_time
    ON user_product_signals (user_id, product_id, occurred_at DESC);

CREATE INDEX idx_product_content_blocks_lookup
    ON product_content_blocks (product_id, language, block_key, audience_key, version DESC)
    WHERE is_active = TRUE;

COMMENT ON TABLE user_product_journeys IS
'Per-product salesperson state. Global users.customer_stage is not used as a replacement for multi-product journey state.';

COMMENT ON TABLE user_product_signals IS
'Unique intent signals prevent repeated button taps from inflating lead score. Raw repeated behavior still belongs in events.';
