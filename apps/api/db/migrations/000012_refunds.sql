-- Durable, idempotent Razorpay refunds. Refunds change payment state only;
-- returned stock is handled separately after a physical return is accepted.
CREATE TABLE IF NOT EXISTS refunds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    payment_id UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    provider_refund_id TEXT UNIQUE,
    idempotency_key TEXT NOT NULL UNIQUE,
    receipt TEXT NOT NULL UNIQUE,
    amount_paise BIGINT NOT NULL CHECK (amount_paise > 0),
    currency CHAR(3) NOT NULL DEFAULT 'INR',
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_refunds_order_status ON refunds(order_id, status);
CREATE INDEX IF NOT EXISTS idx_refunds_provider_payment ON refunds(payment_id);
