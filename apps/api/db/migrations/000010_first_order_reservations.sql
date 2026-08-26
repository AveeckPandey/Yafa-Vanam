-- Reserve the automatic first-order discount before opening Razorpay.
-- The key is per account, so concurrent first checkouts cannot both receive
-- the discount and there is no global coupon row to contend on.
CREATE TABLE IF NOT EXISTS first_order_promotion_reservations (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    promotion_kind TEXT NOT NULL CHECK (promotion_kind IN ('FIRST_ORDER_10')),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, promotion_kind)
);

CREATE INDEX IF NOT EXISTS idx_first_order_reservations_expiry
    ON first_order_promotion_reservations (expires_at);

-- FIRST_ORDER_10 replaces the previous sign-up coupon programme. Historical
-- rows stay for audit purposes, but no WELCOME10 voucher remains redeemable.
UPDATE coupons
   SET is_active = FALSE
 WHERE code LIKE 'WELCOME10-%'
   AND is_active;
