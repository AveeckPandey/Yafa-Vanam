-- Drop tables with no readers/writers anywhere in the codebase.
--
-- The Go API touches only: users, user_credentials, auth_tokens, carts,
-- cart_items, orders, order_items, payments, promotions, coupons,
-- coupon_redemptions, lifecycle_messages, yafa_sessions, user_beauty_profiles,
-- user_shade_history, shades, products, product_variants, categories (the last
-- four are kept because live cart/order rows hold foreign keys into them).
-- Everything below was created speculatively and never wired up.
--
-- CASCADE covers orphan-to-orphan foreign keys (junctions, movements, etc.).

DROP TABLE IF EXISTS product_skin_types CASCADE;
DROP TABLE IF EXISTS skin_types CASCADE;
DROP TABLE IF EXISTS product_concerns CASCADE;
DROP TABLE IF EXISTS concerns CASCADE;
DROP TABLE IF EXISTS product_ingredients CASCADE;
DROP TABLE IF EXISTS ingredients CASCADE;
DROP TABLE IF EXISTS product_images CASCADE;
DROP TABLE IF EXISTS addresses CASCADE;
DROP TABLE IF EXISTS skin_profiles CASCADE;
DROP TABLE IF EXISTS customer_profiles CASCADE;
DROP TABLE IF EXISTS communication_consents CASCADE;
DROP TABLE IF EXISTS wishlist_items CASCADE;
DROP TABLE IF EXISTS return_items CASCADE;
DROP TABLE IF EXISTS return_requests CASCADE;
DROP TABLE IF EXISTS refund_items CASCADE;
DROP TABLE IF EXISTS refunds CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS variant_badges CASCADE;
DROP TABLE IF EXISTS product_badges CASCADE;
DROP TABLE IF EXISTS variant_metrics CASCADE;
DROP TABLE IF EXISTS product_metrics CASCADE;
DROP TABLE IF EXISTS inventory_movements CASCADE;
DROP TABLE IF EXISTS inventory_batches CASCADE;
DROP TABLE IF EXISTS shipments CASCADE;
DROP TABLE IF EXISTS ai_recommendation_feedback CASCADE;
DROP TABLE IF EXISTS ai_recommendations CASCADE;
DROP TABLE IF EXISTS consultation_uploads CASCADE;
DROP TABLE IF EXISTS ai_consultations CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS auth_events CASCADE;
DROP TABLE IF EXISTS auth_sessions CASCADE;
