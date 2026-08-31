-- Restore inventory and reviews as actively used production features. Earlier
-- speculative UUID tables were removed in 000008; these tables use canonical
-- catalogue TEXT ids and match the live commerce implementation.

CREATE TABLE IF NOT EXISTS inventory_levels (
    variant_id TEXT PRIMARY KEY,
    on_hand_quantity INTEGER NOT NULL DEFAULT 0 CHECK (on_hand_quantity >= 0),
    reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 10 CHECK (low_stock_threshold >= 0),
    low_stock_alerted BOOLEAN NOT NULL DEFAULT FALSE,
    version BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (reserved_quantity <= on_hand_quantity)
);

CREATE TABLE IF NOT EXISTS inventory_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    variant_id TEXT NOT NULL REFERENCES inventory_levels(variant_id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL DEFAULT 'RESERVED'
        CHECK (status IN ('RESERVED', 'COMMITTED', 'RELEASED', 'EXPIRED')),
    expires_at TIMESTAMPTZ NOT NULL,
    committed_at TIMESTAMPTZ,
    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (order_id, variant_id)
);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id TEXT NOT NULL REFERENCES inventory_levels(variant_id) ON DELETE RESTRICT,
    order_id UUID REFERENCES orders(id) ON DELETE SET NULL,
    reservation_id UUID REFERENCES inventory_reservations(id) ON DELETE SET NULL,
    movement_type TEXT NOT NULL
        CHECK (movement_type IN ('RECEIPT', 'RESERVATION', 'RELEASE', 'SALE', 'RETURN', 'ADJUSTMENT', 'WRITE_OFF')),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta <> 0),
    reason TEXT,
    actor TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inventory_reservations_expiry
    ON inventory_reservations (expires_at)
    WHERE status = 'RESERVED';
CREATE INDEX IF NOT EXISTS idx_inventory_movements_variant_created
    ON inventory_movements (variant_id, created_at DESC);

-- Transactional outbox for low-stock notifications. The sale and alert are
-- committed atomically; a background dispatcher can safely retry SQS without
-- losing an alert when AWS or the API process is temporarily unavailable.
CREATE TABLE IF NOT EXISTS inventory_alert_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    variant_id TEXT NOT NULL REFERENCES inventory_levels(variant_id) ON DELETE RESTRICT,
    available_quantity INTEGER NOT NULL CHECK (available_quantity >= 0),
    low_stock_threshold INTEGER NOT NULL CHECK (low_stock_threshold >= 0),
    inventory_version BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'SENT')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    locked_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (variant_id, inventory_version)
);

CREATE INDEX IF NOT EXISTS idx_inventory_alert_outbox_dispatch
    ON inventory_alert_outbox (status, created_at)
    WHERE status IN ('PENDING', 'PROCESSING');

-- Release abandoned reservations in one transaction. Invoke this function from
-- a scheduled production job at least once per minute.
CREATE OR REPLACE FUNCTION release_expired_inventory_reservations()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    released_count INTEGER := 0;
BEGIN
    WITH expired AS (
        SELECT id, variant_id, quantity, order_id
        FROM inventory_reservations
        WHERE status = 'RESERVED' AND expires_at <= NOW()
        ORDER BY variant_id, id
        FOR UPDATE SKIP LOCKED
    ), restored AS (
        UPDATE inventory_levels level
        SET reserved_quantity = level.reserved_quantity - expired.quantity,
            version = level.version + 1,
            updated_at = NOW()
        FROM expired
        WHERE level.variant_id = expired.variant_id
        RETURNING expired.id, expired.variant_id, expired.quantity, expired.order_id
    ), marked AS (
        UPDATE inventory_reservations reservation
        SET status = 'EXPIRED', released_at = NOW()
        FROM restored
        WHERE reservation.id = restored.id
        RETURNING restored.*
    )
    INSERT INTO inventory_movements
        (variant_id, order_id, reservation_id, movement_type, quantity_delta, reason, actor)
    SELECT variant_id, order_id, id, 'RELEASE', quantity, 'payment reservation expired', 'system'
    FROM marked;

    GET DIAGNOSTICS released_count = ROW_COUNT;
    RETURN released_count;
END;
$$;

CREATE TABLE IF NOT EXISTS product_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    variant_id TEXT,
    order_item_id UUID NOT NULL UNIQUE REFERENCES order_items(id) ON DELETE RESTRICT,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    body TEXT NOT NULL CHECK (char_length(body) BETWEEN 10 AND 3000),
    display_name TEXT NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 80),
    is_verified_purchase BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'REMOVED')),
    moderation_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_product_reviews_public
    ON product_reviews (product_id, published_at DESC, id DESC)
    WHERE status = 'APPROVED';
CREATE INDEX IF NOT EXISTS idx_product_reviews_user_created
    ON product_reviews (user_id, created_at DESC);

CREATE OR REPLACE VIEW public_product_review_summary AS
SELECT product_id,
       COUNT(*)::INTEGER AS review_count,
       ROUND(AVG(rating)::NUMERIC, 2) AS average_rating
FROM product_reviews
WHERE status = 'APPROVED'
GROUP BY product_id;
