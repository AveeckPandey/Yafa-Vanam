# Analytics

## PostHog

Primary product/user behavior analytics: product views, product clicks, shade selections, wishlist, add-to-cart, checkout funnel, funnels, cohorts, and session replay where configured safely.

## Google Analytics 4

Marketing/acquisition and standardized ecommerce measurement. Important commerce events are mapped to GA4 equivalents in the web analytics layer.

## Consent

Optional analytics must be gated by consent. Essential store operation, order records, fraud/security logs, and payment verification are separate from optional marketing analytics.

## Business truth

PostgreSQL plus verified payment records wins if analytics counts differ from real orders. Bestseller/revenue/refund reporting must not rely on browser analytics event counts.
