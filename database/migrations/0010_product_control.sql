-- SECTION 10 — dashboard-owned Product Control.
-- Keeps the product catalog as data, never Python conditionals.

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0);

ALTER TABLE product_translations
    ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0);

ALTER TABLE product_media
    ADD COLUMN IF NOT EXISTS caption TEXT,
    ADD COLUMN IF NOT EXISTS mime_type TEXT,
    ADD COLUMN IF NOT EXISTS file_name TEXT,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE product_files
    ADD COLUMN IF NOT EXISTS release_notes TEXT,
    ADD COLUMN IF NOT EXISTS mime_type TEXT,
    ADD COLUMN IF NOT EXISTS size_bytes BIGINT CHECK (size_bytes IS NULL OR size_bytes >= 0),
    ADD COLUMN IF NOT EXISTS uploaded_by_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- The commercial rule is structural: discounted orders can never become
-- commissionable by changing a product flag in the dashboard.
UPDATE products SET commission_only_full_price=TRUE WHERE commission_only_full_price IS DISTINCT FROM TRUE;

ALTER TABLE products
    DROP CONSTRAINT IF EXISTS products_commission_only_full_price_locked;
ALTER TABLE products
    ADD CONSTRAINT products_commission_only_full_price_locked
    CHECK (commission_only_full_price IS TRUE);

CREATE TABLE IF NOT EXISTS product_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    target_product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'upsell'
        CHECK (relationship_type IN ('upsell', 'cross_sell', 'next')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_product_id, target_product_id, relationship_type),
    CHECK (source_product_id <> target_product_id)
);

-- Normalize legacy rows before adding one-active-version invariants.
WITH ranked AS (
    SELECT id, row_number() OVER (PARTITION BY product_id, COALESCE(language, '__all__') ORDER BY created_at DESC, id DESC) AS rn
    FROM product_media WHERE media_type='cover' AND is_active=TRUE
)
UPDATE product_media pm SET is_active=FALSE, updated_at=now()
FROM ranked r WHERE pm.id=r.id AND r.rn>1;

WITH ranked AS (
    SELECT id, row_number() OVER (PARTITION BY product_id ORDER BY created_at DESC, id DESC) AS rn
    FROM product_files WHERE is_active=TRUE
)
UPDATE product_files pf SET is_active=FALSE, updated_at=now()
FROM ranked r WHERE pf.id=r.id AND r.rn>1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_active_cover_language
    ON product_media (product_id, COALESCE(language, '__all__'))
    WHERE media_type = 'cover' AND is_active = TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_product_active_delivery_file
    ON product_files (product_id)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_product_media_control
    ON product_media (product_id, is_active, media_type, sort_order, created_at);

CREATE INDEX IF NOT EXISTS idx_product_files_control
    ON product_files (product_id, is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_product_content_control
    ON product_content_blocks (product_id, language, block_key, audience_key, is_active, version DESC);

CREATE INDEX IF NOT EXISTS idx_product_relationships_source
    ON product_relationships (source_product_id, relationship_type, is_active, sort_order);
