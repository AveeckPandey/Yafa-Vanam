# Catalogue data pipeline

Scripts for the normalized catalogue snapshot at `data/processed/Product.json`.
All scripts are stdlib-only Python except the direct DB importer.

```
raw export ──> normalize_products.py ──> data/processed/Product.json
                                              │
                              validate_catalogue.py  (gate — run before import/commit)
                                              │
                    ┌─────────────────────────┴────────────────────────┐
            seed_database.py (SQL file)                 import_catalogue.py (psycopg)
```

## validate_catalogue.py

Enforces the contract the three runtime consumers depend on:

| Consumer | Relies on |
| --- | --- |
| `apps/api/internal/commerce/catalog.go` | unique product ids/slugs/variant ids; non-empty ids on active products |
| `apps/web/lib/catalog.ts` | `description`, `commerce`, `variants`, `images`, `benefits`, `usage`, `warnings`, `ingredients`, `rag` present and typed on every product |
| `services/recommendation-engine` | `status`, shade `code`/`hex`/`undertone`, complexion variant `suitability` |

```bash
python data/scripts/validate_catalogue.py [path] [--strict] [--json]
```

Errors exit `1`; warnings fail only under `--strict`. Exit `2` means unreadable input.
`null` variant stock is valid (commerce truth not yet synced). Shade hex values that
are not `#RRGGBB` (e.g. `"Transparent"`) warn rather than fail because consumers
render them as CSS colors.

## normalize_products.py

Deterministic tidy pass: trims strings, fills documented defaults (`currency=INR`,
`status=draft`, `is_active=true`), slugifies missing slugs, canonicalizes key order,
and normalizes whole-number prices to ints. Product and variant order is preserved —
the snapshot sequence is curated merchandising order, so no re-sorting happens.

```bash
python data/scripts/normalize_products.py [input] [-o OUTPUT] [--check]
```

With no input argument it expects exactly one `*.json` file in `data/raw/`.
`--check` reports drift without writing (exit `1` if the output is out of date),
which suits CI. Output writes atomically via temp-file replace.

## seed_database.py / import_catalogue.py

Both load the catalogue into the `apps/api/db/migrations` schema (categories,
products, shades, product_variants, product_images) with identical row identity:
UUIDv5 derived from catalogue ids, so reruns update instead of duplicate and both
paths produce byte-identical rows. Apply migrations first.

```bash
# Driver-free path: emit SQL, pipe into psql
python data/scripts/seed_database.py --out catalogue_seed.sql
docker compose exec -T postgres psql -U postgres -d yafa_vanam < catalogue_seed.sql

# Direct path (requires: pip install "psycopg[binary]")
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/yafa_vanam?sslmode=disable
python data/scripts/import_catalogue.py          # add --dry-run to project rows only
```

Notes:

- Both run validation first and refuse to proceed on errors unless `--force`.
- Generated SKUs come from uppercased variant ids (`YV-EYE-001-JET-BLACK`) when the
  catalogue leaves `sku` null; the DB enforces uniqueness.
- `stock_quantity` seeds as `0` when catalogue stock is `null`; sync commerce truth
  before relying on stock-backed availability.
- Images are imported only when `images.paths_verified` is true; the storefront
  currently sources imagery from its own manifest, so this is typically zero rows.
