CREATE TABLE conversation_sessions (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    active_flow TEXT NOT NULL DEFAULT 'entry',
    step_key TEXT NOT NULL DEFAULT 'start',
    focus_product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    focus_tracking_link_id UUID REFERENCES tracking_links(id) ON DELETE SET NULL,
    referral_attribution_id UUID REFERENCES referral_attributions(id) ON DELETE SET NULL,
    last_start_kind TEXT NOT NULL DEFAULT 'empty',
    last_start_payload TEXT NOT NULL DEFAULT '',
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_interaction_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversation_sessions_focus_product
    ON conversation_sessions (focus_product_id)
    WHERE focus_product_id IS NOT NULL;

CREATE INDEX idx_conversation_sessions_tracking
    ON conversation_sessions (focus_tracking_link_id)
    WHERE focus_tracking_link_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_sources_user_created
    ON user_sources (user_id, created_at DESC);

CREATE INDEX idx_events_user_type_time
    ON events (user_id, event_type, occurred_at DESC);

COMMENT ON TABLE conversation_sessions IS
'Persistent Telegram conversation cursor. This replaces ephemeral in-memory FSM for customer-critical flows.';
