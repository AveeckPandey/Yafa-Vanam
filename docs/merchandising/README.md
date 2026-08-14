# Merchandising engine

Implemented in Go as a deterministic module.

- BEST_SELLER: based primarily on verified net units/revenue over a configured window.
- TRENDING: combines recent sales velocity/growth with aggregated behavior signals.
- TOP_RATED: rating threshold plus sufficient verified review volume.
- NEW / LOW_STOCK: launch/inventory rules.
- Manual marketing/editorial badges remain possible as explicit overrides.

Product-level and variant/shade-level rankings are separate so a product can be a bestseller while a specific shade such as Berry is also its bestselling variant.
