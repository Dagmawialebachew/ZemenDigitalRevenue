CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT NOT NULL UNIQUE,
    username TEXT,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT,
    telegram_language_code TEXT,
    preferred_language TEXT CHECK (preferred_language IS NULL OR preferred_language IN ('am', 'en')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'deleted')),
    customer_stage TEXT NOT NULL DEFAULT 'new' CHECK (customer_stage IN (
        'new', 'onboarding', 'exploring', 'product_interested', 'high_intent',
        'buy_clicked', 'awaiting_payment', 'proof_submitted', 'payment_rejected',
        'customer', 'repeat_customer'
    )),
    is_bot_blocked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    role TEXT CHECK (role IS NULL OR role IN ('student', 'professional', 'job_seeker', 'business_owner', 'other')),
    ai_experience TEXT CHECK (ai_experience IS NULL OR ai_experience IN ('never_used', 'tried_confused', 'occasional', 'frequent')),
    main_goal TEXT CHECK (main_goal IS NULL OR main_goal IN ('learn_faster', 'work_smarter', 'grow_business', 'find_opportunities', 'save_time', 'other')),
    main_obstacle TEXT CHECK (main_obstacle IS NULL OR main_obstacle IN ('dont_know_what_to_ask', 'poor_answers', 'amharic_uncertainty', 'dont_know_use_cases', 'needs_practical_use', 'other')),
    onboarding_completed_at TIMESTAMPTZ,
    profile_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'hidden', 'archived')),
    product_type TEXT NOT NULL DEFAULT 'digital_file' CHECK (product_type IN ('digital_file', 'digital_bundle', 'course', 'service', 'other')),
    category TEXT,
    default_language TEXT NOT NULL DEFAULT 'am' CHECK (default_language IN ('am', 'en')),
    regular_price_br NUMERIC(12,2) NOT NULL CHECK (regular_price_br > 0),
    recovery_price_br NUMERIC(12,2) CHECK (recovery_price_br IS NULL OR (recovery_price_br > 0 AND recovery_price_br < regular_price_br)),
    discounts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    referral_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    referral_commission_percent NUMERIC(5,2) NOT NULL DEFAULT 10.00 CHECK (referral_commission_percent >= 0 AND referral_commission_percent <= 100),
    commission_only_full_price BOOLEAN NOT NULL DEFAULT TRUE,
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_translations (
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    language TEXT NOT NULL CHECK (language IN ('am', 'en')),
    title TEXT NOT NULL,
    subtitle TEXT,
    short_description TEXT,
    description TEXT,
    benefits JSONB NOT NULL DEFAULT '[]'::jsonb,
    faq JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, language)
);

CREATE TABLE product_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    language TEXT CHECK (language IS NULL OR language IN ('am', 'en')),
    media_type TEXT NOT NULL CHECK (media_type IN ('cover', 'gallery', 'preview', 'video', 'thumbnail', 'other')),
    storage_type TEXT NOT NULL DEFAULT 'url' CHECK (storage_type IN ('telegram_file_id', 'url', 'object_storage')),
    value TEXT NOT NULL,
    alt_text TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE product_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    telegram_file_id TEXT,
    telegram_file_unique_id TEXT,
    object_storage_key TEXT,
    file_name TEXT NOT NULL,
    sha256 TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, version)
);

CREATE TABLE product_content_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    language TEXT NOT NULL CHECK (language IN ('am', 'en')),
    block_key TEXT NOT NULL,
    audience_key TEXT NOT NULL DEFAULT 'default',
    content JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (product_id, language, block_key, audience_key, version)
);

CREATE TABLE tracking_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token TEXT NOT NULL UNIQUE CHECK (char_length(token) BETWEEN 1 AND 60),
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    source TEXT NOT NULL,
    platform TEXT,
    campaign TEXT,
    ad_set TEXT,
    creative TEXT,
    angle TEXT,
    language_hint TEXT CHECK (language_hint IS NULL OR language_hint IN ('am', 'en')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE user_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tracking_link_id UUID REFERENCES tracking_links(id) ON DELETE SET NULL,
    raw_start_payload TEXT NOT NULL DEFAULT '',
    touch_type TEXT NOT NULL CHECK (touch_type IN ('first', 'revisit', 'organic', 'referral')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE referral_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE CHECK (char_length(code) BETWEEN 4 AND 60),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE referral_attributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referral_account_id UUID NOT NULL REFERENCES referral_accounts(id) ON DELETE RESTRICT,
    referrer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    referred_user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    first_product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'void')),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (referrer_user_id <> referred_user_id)
);

CREATE TABLE discount_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL DEFAULT 'recovery' CHECK (rule_type IN ('recovery', 'manual', 'campaign')),
    target_price_br NUMERIC(12,2) NOT NULL CHECK (target_price_br > 0),
    eligibility_delay_seconds INTEGER NOT NULL DEFAULT 0 CHECK (eligibility_delay_seconds >= 0),
    expires_after_seconds INTEGER CHECK (expires_after_seconds IS NULL OR expires_after_seconds > 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    discount_rule_id UUID REFERENCES discount_rules(id) ON DELETE SET NULL,
    original_price_br NUMERIC(12,2) NOT NULL CHECK (original_price_br > 0),
    offer_price_br NUMERIC(12,2) NOT NULL CHECK (offer_price_br > 0),
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'available', 'redeemed', 'expired', 'revoked')),
    eligible_at TIMESTAMPTZ,
    starts_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    redeemed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (offer_price_br < original_price_br),
    CHECK (expires_at IS NULL OR starts_at IS NULL OR expires_at > starts_at)
);

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id TEXT NOT NULL UNIQUE,
    request_key TEXT UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'created' CHECK (status IN (
        'created', 'awaiting_payment', 'proof_submitted', 'under_review',
        'needs_new_proof', 'paid', 'cancelled', 'expired', 'refunded'
    )),
    currency CHAR(3) NOT NULL DEFAULT 'ETB',
    subtotal_br NUMERIC(12,2) NOT NULL CHECK (subtotal_br >= 0),
    discount_total_br NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_total_br >= 0),
    total_due_br NUMERIC(12,2) NOT NULL CHECK (total_due_br >= 0),
    pricing_type TEXT NOT NULL DEFAULT 'regular' CHECK (pricing_type IN ('regular', 'recovery', 'manual_discount')),
    customer_offer_id UUID REFERENCES customer_offers(id) ON DELETE SET NULL,
    source_tracking_link_id UUID REFERENCES tracking_links(id) ON DELETE SET NULL,
    referral_attribution_id UUID REFERENCES referral_attributions(id) ON DELETE SET NULL,
    paid_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (total_due_br = subtotal_br - discount_total_br),
    CHECK ((pricing_type = 'regular' AND discount_total_br = 0) OR (pricing_type <> 'regular' AND discount_total_br > 0))
);

CREATE TABLE order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    regular_unit_price_br NUMERIC(12,2) NOT NULL CHECK (regular_unit_price_br > 0),
    unit_price_br NUMERIC(12,2) NOT NULL CHECK (unit_price_br > 0),
    discount_per_unit_br NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount_per_unit_br >= 0),
    commissionable BOOLEAN NOT NULL DEFAULT TRUE,
    referral_rate_percent_snapshot NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (referral_rate_percent_snapshot >= 0 AND referral_rate_percent_snapshot <= 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (unit_price_br = regular_unit_price_br - discount_per_unit_br),
    CHECK (discount_per_unit_br = 0 OR commissionable = FALSE),
    UNIQUE (order_id, product_id)
);

CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id BIGINT UNIQUE,
    email TEXT UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('owner', 'admin', 'operator', 'viewer')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('cbe', 'telebirr', 'other_manual', 'telegram_stars', 'future_provider')),
    expected_amount_br NUMERIC(12,2) NOT NULL CHECK (expected_amount_br > 0),
    status TEXT NOT NULL DEFAULT 'awaiting_proof' CHECK (status IN ('awaiting_proof', 'pending_review', 'approved', 'rejected', 'flagged', 'cancelled')),
    rejection_reason_code TEXT,
    rejection_reason_text TEXT,
    reviewed_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    submission_key TEXT UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payment_proofs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    telegram_file_id TEXT NOT NULL,
    telegram_file_unique_id TEXT,
    submitted_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    proof_status TEXT NOT NULL DEFAULT 'submitted' CHECK (proof_status IN ('submitted', 'accepted', 'rejected', 'superseded', 'flagged')),
    caption TEXT,
    image_sha256 TEXT,
    verifier_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE entitlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    granted_by_order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    product_file_id UUID REFERENCES product_files(id) ON DELETE SET NULL,
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending', 'queued', 'delivered', 'failed', 'revoked')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (user_id, product_id)
);

CREATE TABLE commissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referral_attribution_id UUID NOT NULL REFERENCES referral_attributions(id) ON DELETE RESTRICT,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    order_item_id UUID NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE RESTRICT,
    referrer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    buyer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    gross_paid_br NUMERIC(12,2) NOT NULL CHECK (gross_paid_br > 0),
    rate_percent NUMERIC(5,2) NOT NULL CHECK (rate_percent >= 0 AND rate_percent <= 100),
    amount_br NUMERIC(12,2) NOT NULL CHECK (amount_br >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'available', 'paid', 'void')),
    available_at TIMESTAMPTZ,
    paid_at TIMESTAMPTZ,
    rule_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (referrer_user_id <> buyer_user_id)
);

CREATE TABLE commission_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    amount_br NUMERIC(12,2) NOT NULL CHECK (amount_br > 0),
    payout_method TEXT NOT NULL CHECK (payout_method IN ('cbe', 'telebirr', 'other')),
    payout_destination TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'paid', 'failed', 'cancelled')),
    processed_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    processed_at TIMESTAMPTZ,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE commission_payout_items (
    payout_id UUID NOT NULL REFERENCES commission_payouts(id) ON DELETE CASCADE,
    commission_id UUID NOT NULL UNIQUE REFERENCES commissions(id) ON DELETE RESTRICT,
    amount_br NUMERIC(12,2) NOT NULL CHECK (amount_br > 0),
    PRIMARY KEY (payout_id, commission_id)
);

CREATE TABLE events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    tracking_link_id UUID REFERENCES tracking_links(id) ON DELETE SET NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE broadcasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'cancelled', 'failed')),
    audience_definition JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_am JSONB,
    content_en JSONB,
    scheduled_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE broadcast_recipients (
    broadcast_id UUID NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'sent', 'failed', 'blocked', 'skipped')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    sent_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ,
    converted_order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    last_error TEXT,
    PRIMARY KEY (broadcast_id, user_id)
);

CREATE TABLE automations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    trigger_event TEXT NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    stop_conditions JSONB NOT NULL DEFAULT '[]'::jsonb,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE automation_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id UUID NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    step_key TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    step_type TEXT NOT NULL CHECK (step_type IN ('wait', 'send_message', 'condition', 'create_offer', 'expire_offer', 'stop', 'other')),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (automation_id, step_key),
    UNIQUE (automation_id, sort_order)
);

CREATE TABLE automation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id UUID NOT NULL REFERENCES automations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'waiting', 'completed', 'stopped', 'failed')),
    current_step_key TEXT,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_run_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    job_key TEXT UNIQUE,
    job_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    priority SMALLINT NOT NULL DEFAULT 100,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    last_error TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    rating SMALLINT CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    review_text TEXT,
    language TEXT CHECK (language IS NULL OR language IN ('am', 'en')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    featured BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id TEXT NOT NULL UNIQUE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    product_id UUID REFERENCES products(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'waiting_customer', 'waiting_admin', 'resolved', 'closed')),
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    subject TEXT,
    assigned_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support_messages (
    id BIGSERIAL PRIMARY KEY,
    case_id UUID NOT NULL REFERENCES support_cases(id) ON DELETE CASCADE,
    sender_type TEXT NOT NULL CHECK (sender_type IN ('user', 'admin', 'system')),
    sender_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    sender_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    telegram_message_id BIGINT,
    body TEXT,
    attachment JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (body IS NOT NULL OR attachment IS NOT NULL)
);

CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('system', 'admin', 'user')),
    actor_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_data JSONB,
    after_data JSONB,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
