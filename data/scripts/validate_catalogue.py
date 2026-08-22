"""Validate the normalized YAFA VANAM catalogue against its consumers' contract.

Consumers and the rules they enforce:
- apps/api/internal/commerce/catalog.go fails hard on duplicate product ids/slugs,
  duplicate or missing variant ids, and active products without an id or slug.
- apps/web/lib/catalog.ts dereferences description, commerce, variants, images,
  benefits, usage, warnings, ingredients and rag on every product.
- services/recommendation-engine shade matching reads shade.code/hex/undertone and
  variant.suitability on complexion products.

Usage:
    python validate_catalogue.py [path] [--strict] [--json]

Exit codes: 0 = no errors (warnings tolerated unless --strict), 1 = failures found,
2 = the file could not be read at all.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_CATALOGUE = Path(__file__).resolve().parents[1] / "processed" / "Product.json"

KNOWN_STATUSES = {"active", "draft", "archived", "discontinued"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEX_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
# Foundation-like types whose variants drive the shade matcher.
EXACT_MATCH_TYPES = {"Foundation", "Skin Tint", "Powder Foundation", "Concealer", "Color Corrector"}

REQUIRED_PRODUCT_STRINGS = ("id", "name", "slug", "brand", "category", "subcategory", "product_type", "status")


class Finding:
    __slots__ = ("severity", "location", "message")

    def __init__(self, severity: str, location: str, message: str) -> None:
        self.severity = severity
        self.location = location
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"severity": self.severity, "location": self.location, "message": self.message}


def _error(location: str, message: str) -> Finding:
    return Finding("error", location, message)


def _warning(location: str, message: str) -> Finding:
    return Finding("warning", location, message)


def _is_list(value: Any) -> bool:
    return isinstance(value, list)


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _check_shade(location: str, shade: Any, findings: list[Finding]) -> None:
    if shade is None:
        return
    if not isinstance(shade, dict):
        findings.append(_error(location, "shade must be an object or null"))
        return
    hex_value = shade.get("hex")
    if hex_value is not None and not (isinstance(hex_value, str) and HEX_PATTERN.match(hex_value)):
        findings.append(
            _warning(location, f"shade hex {hex_value!r} is not #RRGGBB; consumers render it as a CSS color")
        )
    for key in ("name", "code", "undertone", "depth_family"):
        value = shade.get(key)
        if value is not None and not isinstance(value, str):
            findings.append(_error(location, f"shade.{key} must be a string or null"))


def _check_variant_suitability(location: str, variant: dict[str, Any], findings: list[Finding]) -> None:
    suitability = variant.get("suitability")
    if suitability is None:
        return
    if not isinstance(suitability, dict):
        findings.append(_error(location, "suitability must be an object or null"))
        return
    for key in ("best_for_depths", "compatible_depths", "best_for_undertones", "compatible_undertones"):
        value = suitability.get(key)
        if value is not None and not _is_str_list(value):
            findings.append(_error(location, f"suitability.{key} must be a list of strings or null"))


def _check_variant(index: int, product: dict[str, Any], seen_variant_ids: dict[str, str],
                   seen_skus: dict[str, str], findings: list[Finding]) -> None:
    location = f"product {product.get('id') or '?'} variant[{index}]"
    variant = product.get("variants")[index]
    if not isinstance(variant, dict):
        findings.append(_error(location, "variant must be an object"))
        return

    variant_id = variant.get("id")
    if not isinstance(variant_id, str) or not variant_id.strip():
        findings.append(_error(location, "variant.id is required (Go rejects empty variant ids)"))
    elif variant_id in seen_variant_ids:
        findings.append(_error(location, f"duplicate variant id {variant_id!r} (also at {seen_variant_ids[variant_id]})"))
    else:
        seen_variant_ids[variant_id] = location

    price = variant.get("price")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price < 0:
        findings.append(_error(location, f"variant.price must be a non-negative number, got {price!r}"))

    if not isinstance(variant.get("is_active"), bool):
        findings.append(_error(location, "variant.is_active must be a boolean"))

    stock = variant.get("stock")
    if stock is not None and (not isinstance(stock, int) or isinstance(stock, bool) or stock < 0):
        # null stock means commerce truth has not been synced and is expected.
        findings.append(_error(location, "variant.stock must be null or a non-negative integer"))

    size = variant.get("size")
    if size is not None and not isinstance(size, str):
        findings.append(_error(location, "variant.size must be a string or null"))

    sku = variant.get("sku")
    if sku is not None:
        if not isinstance(sku, str) or not sku.strip():
            findings.append(_error(location, "variant.sku must be a non-empty string or null"))
        elif sku in seen_skus:
            findings.append(_error(location, f"duplicate sku {sku!r} (also at {seen_skus[sku]}); the database enforces UNIQUE(sku)"))
        else:
            seen_skus[sku] = location

    _check_shade(location, variant.get("shade"), findings)
    if product.get("product_type") in EXACT_MATCH_TYPES:
        _check_variant_suitability(location, variant, findings)


def _check_product(index: int, product: Any, seen: dict[str, dict[str, str]], findings: list[Finding]) -> None:
    if not isinstance(product, dict):
        findings.append(_error(f"products[{index}]", "product must be an object"))
        return
    product_id = product.get("id") or "?"
    location = f"product {product_id}"

    for key in REQUIRED_PRODUCT_STRINGS:
        value = product.get(key)
        if not isinstance(value, str) or not value.strip():
            findings.append(_error(location, f"{key} is required and must be a non-empty string"))

    slug = product.get("slug")
    if isinstance(slug, str) and slug and not SLUG_PATTERN.match(slug):
        findings.append(_warning(location, f"slug {slug!r} is not kebab-case"))

    if isinstance(product.get("legacy_id"), str) and product["legacy_id"]:
        seen["legacy_id"].setdefault(product["legacy_id"], location)

    for key in ("id", "slug"):
        value = product.get(key)
        if isinstance(value, str) and value:
            if value in seen[key]:
                findings.append(_error(location, f"duplicate product {key} {value!r} (also at {seen[key][value]})"))
            else:
                seen[key][value] = location

    status = product.get("status")
    if isinstance(status, str) and status not in KNOWN_STATUSES:
        findings.append(_warning(location, f"status {status!r} is not one of {sorted(KNOWN_STATUSES)}"))

    description = product.get("description")
    if not isinstance(description, dict) or not isinstance(description.get("short"), str) \
            or not isinstance(description.get("full"), str):
        findings.append(_error(location, "description.{short,full} strings are required (web dereferences them)"))

    commerce = product.get("commerce")
    if not isinstance(commerce, dict):
        findings.append(_error(location, "commerce object is required"))
    else:
        currency = commerce.get("currency")
        if currency is None or currency == "":
            findings.append(_warning(location, "commerce.currency is empty; Go defaults it to INR — set it explicitly"))
        elif not (isinstance(currency, str) and CURRENCY_PATTERN.match(currency)):
            findings.append(_error(location, f"commerce.currency {currency!r} must be a 3-letter ISO code"))
        base_price = commerce.get("base_price")
        if not isinstance(base_price, (int, float)) or isinstance(base_price, bool) or base_price <= 0:
            findings.append(_error(location, f"commerce.base_price must be a positive number, got {base_price!r}"))
        compare_at = commerce.get("compare_at_price")
        if compare_at is not None and (not isinstance(compare_at, (int, float)) or isinstance(compare_at, bool)):
            findings.append(_error(location, "commerce.compare_at_price must be a number or null"))
        elif isinstance(compare_at, (int, float)) and isinstance(base_price, (int, float)) and compare_at < base_price:
            findings.append(_warning(location, "commerce.compare_at_price is below base_price"))

    variants = product.get("variants")
    if not _is_list(variants):
        findings.append(_error(location, "variants must be a list"))
    else:
        if status == "active" and not variants:
            findings.append(_error(location, "active product has no variants; add-to-cart resolves a variant id"))
        seen_variant_ids: dict[str, str] = {}
        seen_skus: dict[str, str] = {}
        for variant_index, _ in enumerate(variants):
            _check_variant(variant_index, product, seen_variant_ids, seen_skus, findings)
        if status == "active" and variants and not any(v.get("is_active") for v in variants if isinstance(v, dict)):
            findings.append(_warning(location, "active product has no active variants"))

    images = product.get("images")
    if not isinstance(images, dict):
        findings.append(_error(location, "images object is required (web dereferences it)"))
    else:
        if not isinstance(images.get("paths_verified"), bool):
            findings.append(_error(location, "images.paths_verified must be a boolean"))
        for key in ("gallery", "lifestyle", "detail"):
            if not _is_str_list(images.get(key, [])):
                findings.append(_error(location, f"images.{key} must be a list of strings"))
        for key in ("primary", "texture", "alt"):
            value = images.get(key)
            if value is not None and not isinstance(value, str):
                findings.append(_error(location, f"images.{key} must be a string or null"))
        if images.get("paths_verified") and not images.get("primary"):
            findings.append(_warning(location, "images.paths_verified is true but images.primary is empty"))

    if not _is_str_list(product.get("benefits", [])):
        findings.append(_error(location, "benefits must be a list of strings"))

    usage = product.get("usage")
    if not isinstance(usage, dict) or not isinstance(usage.get("how_to_use"), str):
        findings.append(_error(location, "usage.how_to_use is required (web dereferences it)"))
    elif usage and not _is_str_list(usage.get("when", [])):
        findings.append(_error(location, "usage.when must be a list of strings"))

    if not _is_str_list(product.get("warnings", [])):
        findings.append(_error(location, "warnings must be a list of strings"))

    ingredients = product.get("ingredients")
    if not isinstance(ingredients, dict):
        findings.append(_error(location, "ingredients object is required (web dereferences it)"))
    else:
        active_ingredients = ingredients.get("active_ingredients", [])
        if not _is_list(active_ingredients):
            findings.append(_error(location, "ingredients.active_ingredients must be a list"))
        else:
            # Entries are structured ingredient records, matching the Go []any contract.
            for ingredient_index, ingredient in enumerate(active_ingredients):
                ingredient_location = f"{location} ingredients.active_ingredients[{ingredient_index}]"
                if not isinstance(ingredient, dict) or not isinstance(ingredient.get("name"), str) \
                        or not ingredient["name"].strip():
                    findings.append(_error(ingredient_location, "needs a non-empty name string"))
                    continue
                for key in ("role", "source", "evidence_level", "concentration"):
                    if ingredient.get(key) is not None and not isinstance(ingredient[key], str):
                        findings.append(_error(ingredient_location, f"{key} must be a string or null"))
                for key in ("verified_for_final_formula", "concentration_dependent_claims"):
                    if ingredient.get(key) is not None and not isinstance(ingredient[key], bool):
                        findings.append(_error(ingredient_location, f"{key} must be a boolean or null"))
        for key in ("full_inci", "ingredient_data_note"):
            value = ingredients.get(key)
            if value is not None and not isinstance(value, str):
                findings.append(_error(location, f"ingredients.{key} must be a string or null"))

    rag = product.get("rag")
    if not isinstance(rag, dict):
        findings.append(_error(location, "rag object is required (web dereferences rag.customer_questions)"))
    else:
        questions = rag.get("customer_questions", [])
        if not _is_list(questions):
            findings.append(_error(location, "rag.customer_questions must be a list"))
        else:
            for question_index, question in enumerate(questions):
                if not isinstance(question, dict) or not isinstance(question.get("question"), str) \
                        or not isinstance(question.get("answer"), str):
                    findings.append(_error(location, f"rag.customer_questions[{question_index}] needs question and answer strings"))

    recommendation_profile = product.get("recommendation_profile")
    if recommendation_profile is not None and not isinstance(recommendation_profile, dict):
        findings.append(_error(location, "recommendation_profile must be an object or null"))


def validate_catalogue(products: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not _is_list(products):
        return [_error("root", "catalogue must be a JSON array")]
    if not products:
        return [_error("root", "catalogue contains no products")]

    seen: dict[str, dict[str, str]] = {"id": {}, "slug": {}, "legacy_id": {}}
    for index, product in enumerate(products):
        _check_product(index, product, seen, findings)
    return findings


def load_catalogue(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the YAFA VANAM catalogue JSON.")
    parser.add_argument("path", nargs="?", default=str(DEFAULT_CATALOGUE), help="catalogue JSON path")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        products = load_catalogue(path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"cannot read catalogue {path}: {exc}", file=sys.stderr)
        return 2

    findings = validate_catalogue(products)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    failed = bool(errors) or (args.strict and bool(warnings))

    if args.json:
        print(json.dumps({
            "path": str(path),
            "products": len(products),
            "failed": failed,
            "errors": [f.as_dict() for f in errors],
            "warnings": [f.as_dict() for f in warnings],
        }, indent=2))
    else:
        print(f"Catalogue: {path} ({len(products)} products)")
        for finding in findings:
            marker = "ERROR" if finding.severity == "error" else "WARN "
            print(f"  [{marker}] {finding.location}: {finding.message}")
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
        print("FAILED" if failed else "OK")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
