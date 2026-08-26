# Database schema

The PostgreSQL schema lives in `apps/api/db/migrations/`. Apply migrations in
numeric order: `000001_core_schema.sql`, then `000002_production_hardening.sql`.

Core entities include Category, Product, Shade, ProductVariant/SKU, ProductImage, User, CustomerProfile, CommunicationConsent, Order, OrderItem, Payment, Refund/RefundItem, ReturnRequest/ReturnItem, Review, ProductMetrics, VariantMetrics, ProductBadge, VariantBadge, Promotion, Coupon, and LifecycleMessage.

A product is the customer-facing item; a variant is the exact sellable combination (for example Berry / 4 ml); the SKU uniquely identifies that variant for inventory and order operations.

## Production decisions

- Authentication is custom. `user_credentials` holds only an Argon2id password
  hash, while `auth_sessions` and `auth_tokens` hold hashes of opaque tokens.
- Images never live in PostgreSQL. Product image URLs point to public Cloudflare
  R2 assets; consultation uploads retain only a private R2 bucket/object key.
- `inventory_batches` owns manufacture and expiry dates. Product-level
  `best_before_months` is a shelf-life rule, not an actual expiry.
- `order_items` preserves the price, SKU, product name, and batch expiry that
  applied at checkout, so later catalogue or batch changes do not rewrite history.
- `products.vector_id` is the external Qdrant reference; vectors are not stored
  in Railway PostgreSQL.
- Promotions are account-bound (migration `000009`). There are exactly two
  programmes: `FIRST_ORDER_10` applies automatically to a signed-in,
  email-verified user's first successfully paid order — no coupon code exists —
  with the once-per-user guarantee enforced by `UNIQUE (user_id, promotion_kind)`
  on `user_promotion_redemptions`; `YV_20` service-recovery vouchers are
  per-user coupon rows (`coupons.user_id`) that require sign-in to redeem, are
  single-use, expire in 30 days, and can be revoked until redeemed. The shared
  public codes (`YAFA20`, `NATURE15`, `FLAT500`, `WELCOME10`) are deactivated;
  their rows remain only so historical redemptions keep their references.
