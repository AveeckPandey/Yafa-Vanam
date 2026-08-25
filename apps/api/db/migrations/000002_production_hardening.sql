-- YAFA VANAM production hardening for Railway PostgreSQL.
-- Apply after 000001_core_schema.sql. Image bytes remain in Cloudflare R2;
-- this database records object keys and metadata only.

-- Product rules belong to the catalogue. Actual manufacture/expiry dates belong
-- to inventory_batches because they differ for every received batch.
ALTER TABLE products
    ADD COLUMN IF NOT EXISTS best_before_months INTEGER CHECK (best_before_months > 0),
    ADD COLUMN IF NOT EXISTS vector_id TEXT;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_lower
    ON users (LOWER(email));

-- Custom authentication. Only a bcrypt (cost 12) hash is stored; never store a password.
CREATE TABLE IF NOT EXISTS user_credentials (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failed_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempt_count >= 0),
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expires_at > created_at)
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    token_type TEXT NOT NULL CHECK (token_type IN ('EMAIL_VERIFICATION', 'PASSWORD_RESET')),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expires_at > created_at)
);

CREATE TABLE IF NOT EXISTS auth_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    email_attempted TEXT,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Perishable inventory is batch based. product_variants.stock_quantity remains
-- a denormalized availability cache for backwards compatibility.
CREATE TABLE IF NOT EXISTS inventory_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id UUID NOT NULL REFERENCES product_variants(id) ON DELETE RESTRICT,
    batch_number TEXT NOT NULL,
    manufactured_at DATE,
    expires_at DATE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    unit_cost NUMERIC(12,2) CHECK (unit_cost >= 0),
    quantity_received INTEGER NOT NULL CHECK (quantity_received >= 0),
    quantity_available INTEGER NOT NULL CHECK (quantity_available >= 0),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'QUARANTINED', 'EXPIRED', 'RECALLED', 'DEPLETED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (variant_id, batch_number),
    CHECK (expires_at IS NULL OR manufactured_at IS NULL OR expires_at >= manufactured_at),
    CHECK (quantity_available <= quantity_received)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES inventory_batches(id) ON DELETE RESTRICT,
    order_item_id UUID REFERENCES order_items(id) ON DELETE SET NULL,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('RECEIPT', 'RESERVATION', 'RELEASE', 'SALE', 'RETURN', 'ADJUSTMENT', 'WRITE_OFF')),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta <> 0),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE order_items
    ADD COLUMN IF NOT EXISTS inventory_batch_id UUID REFERENCES inventory_batches(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS expiration_date_snapshot DATE,
    ADD COLUMN IF NOT EXISTS currency CHAR(3) NOT NULL DEFAULT 'INR';

-- Preserve every applied discount independently of later coupon edits.
ALTER TABLE coupons
    ADD COLUMN IF NOT EXISTS per_user_limit INTEGER NOT NULL DEFAULT 1 CHECK (per_user_limit > 0),
    ADD COLUMN IF NOT EXISTS max_discount_cap NUMERIC(12,2) CHECK (max_discount_cap >= 0),
    ADD COLUMN IF NOT EXISTS minimum_order_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (minimum_order_amount >= 0),
    ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE RESTRICT,
    order_id UUID NOT NULL UNIQUE REFERENCES orders(id) ON DELETE RESTRICT,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    code_snapshot TEXT NOT NULL,
    discount_amount NUMERIC(12,2) NOT NULL CHECK (discount_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    carrier TEXT,
    tracking_number TEXT,
    tracking_url TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PACKED', 'SHIPPED', 'IN_TRANSIT', 'DELIVERED', 'FAILED', 'RETURNED')),
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (carrier, tracking_number)
);

-- AI consultation records are consent-aware. Customer photos are private R2
-- objects and must only be read through short-lived URLs issued by the backend.
CREATE TABLE IF NOT EXISTS ai_consultations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    anonymous_key TEXT,
    status TEXT NOT NULL DEFAULT 'STARTED' CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED', 'DELETED')),
    consented_at TIMESTAMPTZ,
    consent_version TEXT,
    quiz_answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (user_id IS NOT NULL OR anonymous_key IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS consultation_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES ai_consultations(id) ON DELETE CASCADE,
    bucket TEXT NOT NULL DEFAULT 'yafa-private',
    object_key TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,
    bytes INTEGER NOT NULL CHECK (bytes > 0),
    sha256 TEXT,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES ai_consultations(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    variant_id UUID REFERENCES product_variants(id) ON DELETE SET NULL,
    rank INTEGER NOT NULL CHECK (rank > 0),
    score DOUBLE PRECISION CHECK (score >= 0 AND score <= 1),
    reason TEXT,
    explanation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (consultation_id, product_id, variant_id)
);

CREATE TABLE IF NOT EXISTS ai_recommendation_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES ai_recommendations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    feedback TEXT NOT NULL CHECK (feedback IN ('HELPFUL', 'NOT_HELPFUL', 'PURCHASED', 'DISMISSED')),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (recommendation_id, user_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    ip_address INET,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_active ON auth_sessions (user_id, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_auth_tokens_active ON auth_tokens (user_id, expires_at) WHERE used_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_auth_events_email_created ON auth_events (email_attempted, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_batches_variant_expiry ON inventory_batches (variant_id, expires_at) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_inventory_movements_batch_created ON inventory_movements (batch_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_coupon_redemptions_user_coupon ON coupon_redemptions (user_id, coupon_id);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments (order_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consultations_user_created ON ai_consultations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consultation_uploads_retention ON consultation_uploads (deleted_at, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_consultation_rank ON ai_recommendations (consultation_id, rank);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id, created_at DESC);
