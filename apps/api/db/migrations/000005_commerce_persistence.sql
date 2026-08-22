-- Commerce persistence: make carts/orders/payments durable in PostgreSQL.
--
-- The storefront catalogue lives in Product.json (string IDs like "prod_..." /
-- "var_..."), so item lines cannot carry UUID foreign keys into product tables
-- that are never seeded. Carts and orders therefore keep their UUID primary
-- keys (downstream tables in 000001/000002 depend on them), while item lines
-- snapshot catalogue identifiers as TEXT. Guest access tokens, Razorpay
-- references, and order idempotency keys are added here because the original
-- commerce tables predate the checkout implementation.

-- Guest carts hold neither user_id nor anonymous_key; the original CHECK
-- rejected them.
ALTER TABLE carts DROP CONSTRAINT IF EXISTS carts_check;

-- Catalogue variant IDs are strings, not product_variants.uuid values.
ALTER TABLE cart_items DROP CONSTRAINT IF EXISTS cart_items_variant_id_fkey;
ALTER TABLE cart_items
    ALTER COLUMN variant_id TYPE TEXT USING variant_id::text;

ALTER TABLE orders
    ADD COLUMN access_token TEXT,
    ADD COLUMN razorpay_order_id TEXT,
    ADD COLUMN razorpay_payment_id TEXT,
    ADD COLUMN idempotency_key TEXT,
    ALTER COLUMN order_status SET DEFAULT 'PENDING_PAYMENT';

CREATE UNIQUE INDEX idx_orders_access_token ON orders(access_token) WHERE access_token IS NOT NULL;
CREATE UNIQUE INDEX idx_orders_razorpay_order ON orders(razorpay_order_id) WHERE razorpay_order_id IS NOT NULL;
CREATE UNIQUE INDEX idx_orders_idempotency ON orders(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Order lines snapshot everything the customer saw at purchase time so order
-- history never depends on the live catalogue.
ALTER TABLE order_items DROP CONSTRAINT IF EXISTS order_items_product_id_fkey;
ALTER TABLE order_items DROP CONSTRAINT IF EXISTS order_items_variant_id_fkey;
ALTER TABLE order_items
    ALTER COLUMN product_id TYPE TEXT USING product_id::text,
    ALTER COLUMN variant_id TYPE TEXT USING variant_id::text,
    ADD COLUMN line_key TEXT NOT NULL DEFAULT '',
    ADD COLUMN slug TEXT NOT NULL DEFAULT '',
    ADD COLUMN product_type TEXT NOT NULL DEFAULT '',
    ADD COLUMN size TEXT,
    ADD COLUMN image TEXT;

-- One payment record per order per provider keeps retries idempotent.
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_order_provider_key;
ALTER TABLE payments
    ADD CONSTRAINT payments_order_provider_key UNIQUE (order_id, provider);
CREATE INDEX idx_payments_provider_order ON payments(provider_order_id);
