# Merchandising engine

Owns deterministic product/variant ranking and badges such as BEST_SELLER, TRENDING, TOP_RATED, NEW, and LOW_STOCK.

Best-seller rankings use verified commerce data (paid order items minus returns/refunds), not PostHog or GA4 purchase-event counts. Trending may combine recent sales velocity with aggregated behavior signals.
