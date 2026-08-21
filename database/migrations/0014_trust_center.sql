CREATE TABLE legal_acceptances (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    policy_version TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('am','en')),
    surface TEXT NOT NULL CHECK (surface IN ('telegram','miniapp')),
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, order_id, policy_version)
);

CREATE INDEX idx_legal_acceptances_user_time
    ON legal_acceptances (user_id, accepted_at DESC);

CREATE INDEX idx_support_cases_subject_queue
    ON support_cases (subject, status, updated_at DESC);
