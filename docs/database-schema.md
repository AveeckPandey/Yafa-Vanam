# Database schema

The initial Go/PostgreSQL schema lives in `apps/api/db/migrations/000001_core_schema.sql`.

Core entities include Category, Product, Shade, ProductVariant/SKU, ProductImage, User, CustomerProfile, CommunicationConsent, Order, OrderItem, Payment, Refund/RefundItem, ReturnRequest/ReturnItem, Review, ProductMetrics, VariantMetrics, ProductBadge, VariantBadge, Promotion, Coupon, and LifecycleMessage.

A product is the customer-facing item; a variant is the exact sellable combination (for example Berry / 4 ml); the SKU uniquely identifies that variant for inventory and order operations.
