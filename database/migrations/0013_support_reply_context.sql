CREATE TABLE IF NOT EXISTS support_reply_contexts (
    admin_telegram_id BIGINT PRIMARY KEY,

    case_id UUID NOT NULL
        REFERENCES support_cases(id)
        ON DELETE CASCADE,

    ops_chat_id BIGINT NOT NULL,
    message_thread_id BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 minutes')
);

CREATE INDEX IF NOT EXISTS idx_support_reply_contexts_expires
    ON support_reply_contexts (expires_at);