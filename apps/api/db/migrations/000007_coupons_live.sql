-- Coupons move from hardcoded checkout switches to real rows. This migration
-- (1) records which code each order used so redemption can happen at payment
-- time, (2) makes "one welcome coupon per user" a database guarantee, and
-- (3) seeds the legacy public codes so existing behaviour is preserved.

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS discount_code TEXT NOT NULL DEFAULT '';

-- A user may hold exactly one personalised welcome coupon. The partial unique
-- index lets concurrent PostConfirmation retries race safely: the loser's
-- INSERT fails and it falls back to reading the winner's row.
CREATE UNIQUE INDEX IF NOT EXISTS uq_coupons_one_welcome_per_user
    ON coupons (user_id)
    WHERE code LIKE 'WELCOME10-%';

-- Legacy codes were previously unlimited in checkoutDiscount(). They are
-- seeded with enormous caps to preserve that behaviour; tightening them is a
-- deliberate product decision, not an accident of this migration.
DO $$
DECLARE
    promotion_id UUID;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM coupons WHERE code = 'YAFA20') THEN
        INSERT INTO promotions (name, promotion_type, value, is_active)
        VALUES ('YAFA20 launch offer', 'PERCENTAGE', 20, TRUE)
        RETURNING id INTO promotion_id;
        INSERT INTO coupons (promotion_id, code, max_uses, per_user_limit, minimum_order_amount, is_active)
        VALUES (promotion_id, 'YAFA20', 1000000, 1000000, 0, TRUE);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM coupons WHERE code = 'NATURE15') THEN
        INSERT INTO promotions (name, promotion_type, value, is_active)
        VALUES ('NATURE15 launch offer', 'PERCENTAGE', 15, TRUE)
        RETURNING id INTO promotion_id;
        INSERT INTO coupons (promotion_id, code, max_uses, per_user_limit, minimum_order_amount, is_active)
        VALUES (promotion_id, 'NATURE15', 1000000, 1000000, 0, TRUE);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM coupons WHERE code = 'FLAT500') THEN
        INSERT INTO promotions (name, promotion_type, value, is_active)
        VALUES ('FLAT500 launch offer', 'ABSOLUTE', 500, TRUE)
        RETURNING id INTO promotion_id;
        INSERT INTO coupons (promotion_id, code, max_uses, per_user_limit, minimum_order_amount, is_active)
        VALUES (promotion_id, 'FLAT500', 1000000, 1000000, 0, TRUE);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM coupons WHERE code = 'WELCOME10') THEN
        INSERT INTO promotions (name, promotion_type, value, is_active)
        VALUES ('Welcome 10% offer', 'PERCENTAGE', 10, TRUE)
        RETURNING id INTO promotion_id;
        INSERT INTO coupons (promotion_id, code, max_uses, per_user_limit, minimum_order_amount, is_active)
        VALUES (promotion_id, 'WELCOME10', 1000000, 1000000, 0, TRUE);
    END IF;
END $$;
