-- Account-bound promotions replace shared/public coupon codes.
--
-- (1) promotions gain a `kind` so the two supported programmes are explicit:
--     AUTO_FIRST_ORDER (FIRST_ORDER_10) and SERVICE_RECOVERY (YV_20).
--     Legacy seeded rows stay 'MANUAL_CODE' — existing data is preserved.
-- (2) A user-level redemption ledger gives FIRST_ORDER_10 a database-level
--     once-per-user guarantee: UNIQUE (user_id, promotion_kind) makes retry
--     storms, Razorpay webhook duplicates, and concurrent verifications
--     no-ops without ever locking a shared coupon row (10M+ users scale).
-- (3) The shared public codes seeded by 000007 are DEACTIVATED, not deleted,
--     so historical redemption rows keep their referential integrity while
--     the codes stop working at checkout.
-- (4) Supporting indexes keep eligibility checks and voucher lookups fast.

ALTER TABLE promotions
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'MANUAL_CODE';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'promotions_kind_check'
    ) THEN
        ALTER TABLE promotions ADD CONSTRAINT promotions_kind_check
            CHECK (kind IN ('MANUAL_CODE', 'AUTO_FIRST_ORDER', 'SERVICE_RECOVERY'));
    END IF;
END $$;

DO $$
DECLARE
    promotion_id UUID;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM promotions WHERE name = 'FIRST_ORDER_10') THEN
        INSERT INTO promotions (name, promotion_type, value, kind, is_active)
        VALUES ('FIRST_ORDER_10', 'PERCENTAGE', 10, 'AUTO_FIRST_ORDER', TRUE);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM promotions WHERE name = 'YV_20') THEN
        INSERT INTO promotions (name, promotion_type, value, kind, is_active)
        VALUES ('YV_20', 'PERCENTAGE', 20, 'SERVICE_RECOVERY', TRUE)
        RETURNING id INTO promotion_id;
    END IF;
END $$;

-- User-level redemption ledger for automatic (code-less) programmes. The
-- promotion_kind mirrors orders.discount_code so payment confirmation can
-- record the grant directly. Service-recovery vouchers (YV_20) are per-user
-- coupon rows tracked through coupon_redemptions instead — each voucher is
-- its own single-use row, so support may compensate a user more than once.
CREATE TABLE IF NOT EXISTS user_promotion_redemptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    promotion_kind TEXT NOT NULL CHECK (promotion_kind IN ('FIRST_ORDER_10')),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    discount_amount NUMERIC(12,2) NOT NULL CHECK (discount_amount >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- The once-ever guarantee: retries, duplicate webhooks, and concurrent
    -- payment confirmations all collapse onto this single unique row.
    UNIQUE (user_id, promotion_kind)
);

CREATE INDEX IF NOT EXISTS idx_user_promotion_orders
    ON user_promotion_redemptions (order_id);

-- Paid-order history lookup for FIRST_ORDER_10 eligibility: a partial index
-- stays tiny because most orders never reach a paid status.
CREATE INDEX IF NOT EXISTS idx_orders_user_paid
    ON orders (user_id, created_at)
    WHERE payment_status IN ('AUTHORIZED', 'CAPTURED');

-- Voucher administration and owner-bound lookups.
CREATE INDEX IF NOT EXISTS idx_coupons_user_active
    ON coupons (user_id, is_active)
    WHERE user_id IS NOT NULL;

-- Shared public codes stop working everywhere. Rows are kept so historical
-- coupon_redemptions/lifecycle_messages references remain intact; personalised
-- (user-bound) coupons are untouched.
UPDATE coupons SET is_active = FALSE
 WHERE user_id IS NULL
   AND code IN ('YAFA20', 'NATURE15', 'FLAT500', 'WELCOME10')
   AND is_active;
