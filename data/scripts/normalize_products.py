"""Normalize a raw YAFA VANAM catalogue export into the processed snapshot.

Deterministic tidy pass between the raw export and data/processed/Product.json:
- trims whitespace on every string,
- fills documented defaults (currency INR, status draft, active variants),
- generates a kebab-case slug from the product name when missing,
- normalizes whole-number prices to integers,
- rewrites each record with a canonical key layout while preserving product and
variant order, so diffs against the processed snapshot stay reviewable.

Usage:
    python normalize_products.py [input] [-o OUTPUT] [--check]

With no input argument, exactly one *.json file in data/raw/ is expected.
--check reports whether the processed snapshot is up to date without writing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "Product.json"

DEFAULT_CURRENCY = "INR"
DEFAULT_STATUS = "draft"

# Canonical key layouts; unrecognized keys are preserved after these in sorted order.
PRODUCT_KEY_ORDER = (
    "id", "legacy_id", "name", "slug", "brand", "category", "subcategory",
    "product_type", "status", "launch_date", "description", "commerce", "variants",
    "images", "ingredients", "benefits", "recommendation_profile", "usage", "warnings",
    "compatibility", "rag", "palette_colors", "variant_note", "data_status", "metadata",
    "evidence", "use_area", "regulatory", "eye_safety", "makeup_profile", "claims_review",
    "research_gaps", "shopping_experience", "pdp", "merchandising", "live_data_contract",
    "shade_system", "fragrance_compliance", "fragrance_profile", "sun_protection",
)
VARIANT_KEY_ORDER = ("id", "sku", "size", "shade", "price", "stock", "is_active", "media", "regulatory")
COMMERCE_KEY_ORDER = ("currency", "base_price", "compare_at_price", "tax_code", "pricing_positioning",
                      "pricing_status", "pricing_reviewed_at", "pricing_note")

SLUG_FALLBACK_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return SLUG_FALLBACK_PATTERN.sub("-", value.strip().lower()).strip("-")


def normalize_price(value: Any) -> Any:
    """Render whole-number prices as ints so 4200 and 4200.0 diff identically."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_value(item) for key, item in value.items()}
    return value


def ordered(mapping: dict[str, Any], key_order: tuple[str, ...]) -> dict[str, Any]:
    known = {key: mapping[key] for key in key_order if key in mapping}
    extras = {key: mapping[key] for key in sorted(mapping) if key not in known}
    return {**known, **extras}


def normalize_variant(variant: dict[str, Any]) -> dict[str, Any]:
    variant = normalize_value(variant)
    if not isinstance(variant, dict):
        return variant
    variant.setdefault("is_active", True)
    variant["price"] = normalize_price(variant.get("price"))
    return ordered(variant, VARIANT_KEY_ORDER)


def normalize_product(product: Any) -> Any:
    product = normalize_value(product)
    if not isinstance(product, dict):
        return product

    name = product.get("name") or ""
    if not product.get("slug") and name:
        product["slug"] = slugify(name)

    commerce = product.get("commerce")
    if isinstance(commerce, dict):
        if not commerce.get("currency"):
            commerce["currency"] = DEFAULT_CURRENCY
        commerce["base_price"] = normalize_price(commerce.get("base_price"))
        product["commerce"] = ordered(commerce, COMMERCE_KEY_ORDER)

    status = product.get("status")
    if not status:
        product["status"] = DEFAULT_STATUS

    variants = product.get("variants")
    if isinstance(variants, list):
        # Variant order is merchandising-relevant (default shade is first); preserve it.
        product["variants"] = [normalize_variant(variant) for variant in variants]
    return ordered(product, PRODUCT_KEY_ORDER)


def normalize_catalogue(products: list[Any]) -> list[Any]:
    # Product order is preserved: the snapshot's sequence is curated, not incidental.
    return [normalize_product(product) for product in products]


def find_raw_input(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SystemExit(f"input catalogue not found: {path}")
        return path
    candidates = sorted(RAW_DIR.glob("*.json"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise SystemExit(
            f"no catalogue JSON in {RAW_DIR}; pass an input path or drop the raw export there"
        )
    listed = "\n".join(f"  - {candidate.name}" for candidate in candidates)
    raise SystemExit(f"multiple raw catalogues in {RAW_DIR}; pass one explicitly:\n{listed}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dump_catalogue(products: list[dict[str, Any]], output: Path) -> None:
    payload = json.dumps(products, indent=2, ensure_ascii=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write via temp file + replace so a crash never leaves a truncated snapshot.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                     delete=False, suffix=".tmp") as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    temp_path.replace(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize a raw YAFA VANAM catalogue export.")
    parser.add_argument("input", nargs="?", help="raw catalogue JSON (default: sole file in data/raw)")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="normalized output path")
    parser.add_argument("--check", action="store_true",
                        help="report drift from the output file without writing it")
    args = parser.parse_args(argv)

    input_path = find_raw_input(args.input)
    try:
        products = load_json(input_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read catalogue {input_path}: {exc}")
    if not isinstance(products, list):
        raise SystemExit("catalogue must be a JSON array")

    normalized = normalize_catalogue(products)
    output_path = Path(args.output)

    if args.check:
        current = load_json(output_path) if output_path.is_file() else None
        if current == normalized:
            print(f"OK: {output_path} matches normalization of {input_path}")
            return 0
        print(f"DRIFT: {output_path} does not match normalization of {input_path}", file=sys.stderr)
        return 1

    dump_catalogue(normalized, output_path)
    print(f"wrote {len(normalized)} products to {output_path}")
    print("next: run validate_catalogue.py before importing or committing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
