"""Import the normalized YAFA VANAM catalogue into PostgreSQL.

Upserts the snapshot into the apps/api/db/migrations/000001_core_schema.sql tables:
categories (with subcategory children), products, shades, product_variants and
product_images. Row identity is derived deterministically from catalogue ids via
UUIDv5, so re-running the import updates rather than duplicates.

Requires migrations to be applied first and psycopg 3 to be installed:

    pip install "psycopg[binary]"
    python import_catalogue.py [--catalogue PATH] [--dsn URL] [--dry-run] [--force]

The DSN defaults to $DATABASE_URL. Validation runs first; a failing catalogue
aborts the import unless --force is given.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_catalogue import validate_catalogue  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOGUE = REPO_ROOT / "data" / "processed" / "Product.json"

# Stable UUIDv5 namespace so regenerated rows keep their primary keys across runs.
UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://yafavanam.com/catalogue-import")

STATUS_MAP = {
    "active": "ACTIVE",
    "draft": "DRAFT",
    "archived": "ARCHIVED",
    "discontinued": "DISCONTINUED",
}


def slugify(value: str) -> str:
    return re.compile(r"[^a-z0-9]+").sub("-", value.strip().lower()).strip("-")


def deterministic_uuid(kind: str, key: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"{kind}:{key}"))


def map_status(catalogue_status: Any) -> str:
    return STATUS_MAP.get(str(catalogue_status or "").lower(), "DRAFT")


def build_rows(products: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Project the catalogue onto migration-schema row dicts (no DB access)."""
    parent_categories: dict[str, dict[str, Any]] = {}
    child_categories: dict[tuple[str, str], dict[str, Any]] = {}
    product_rows: list[dict[str, Any]] = []
    shade_rows: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []

    for sort_order, category_name in enumerate(sorted({str(p["category"]) for p in products})):
        parent_categories[category_name] = {
            "id": deterministic_uuid("category", category_name),
            "name": category_name,
            "slug": slugify(category_name),
            "parent_id": None,
            "sort_order": sort_order,
        }

    for product in products:
        category_name = str(product["category"])
        subcategory_name = str(product.get("subcategory") or "")
        child_key = (category_name, subcategory_name)
        if subcategory_name and child_key not in child_categories:
            child_categories[child_key] = {
                "id": deterministic_uuid("category", f"{category_name}/{subcategory_name}"),
                "name": subcategory_name,
                "slug": slugify(subcategory_name),
                "parent_id": parent_categories[category_name]["id"],
                "sort_order": len(child_categories),
            }
        # Subcategory drives storefront filters; fall back to the parent when absent.
        category_id = child_categories[child_key]["id"] if subcategory_name \
            else parent_categories[category_name]["id"]

        product_id_key = str(product["id"])
        product_row_id = deterministic_uuid("product", product_id_key)
        commerce = product.get("commerce") or {}
        usage = product.get("usage") or {}
        description = product.get("description") or {}
        launch_date = product.get("launch_date")

        product_rows.append({
            "id": product_row_id,
            "category_id": category_id,
            "name": product["name"],
            "slug": product["slug"],
            "product_type": product.get("product_type"),
            "short_description": description.get("short"),
            "description": description.get("full"),
            "directions": usage.get("how_to_use"),
            "benefits": [b for b in product.get("benefits") or []],
            "status": map_status(product.get("status")),
            "launch_date": launch_date if isinstance(launch_date, str) and launch_date else None,
        })

        seen_shades: dict[str, str] = {}
        for variant in product.get("variants") or []:
            shade = variant.get("shade") or {}
            shade_name = shade.get("name")
            shade_id = None
            if isinstance(shade_name, str) and shade_name.strip():
                shade_slug = slugify(shade_name)
                shade_id = seen_shades.get(shade_slug)
                if shade_id is None:
                    shade_id = deterministic_uuid(
                        "shade", f"{product_id_key}:{shade_slug}")
                    seen_shades[shade_slug] = shade_id
                    shade_rows.append({
                        "id": shade_id,
                        "product_id": product_row_id,
                        "name": shade_name,
                        "slug": shade_slug,
                        "code": shade.get("code"),
                        "hex": shade.get("hex"),
                        "undertone": shade.get("undertone"),
                    })

            variant_id_key = str(variant["id"])
            # Catalogue ids like yv-eye-001-jet-black already carry the YV prefix.
            sku = variant.get("sku") or variant_id_key.upper()
            variant_rows.append({
                "id": deterministic_uuid("variant", variant_id_key),
                "product_id": product_row_id,
                "shade_id": shade_id,
                "name": shade_name if isinstance(shade_name, str) and shade_name else product["name"],
                "sku": sku,
                "size": variant.get("size"),
                "price": variant.get("price"),
                "compare_at_price": commerce.get("compare_at_price"),
                "currency": commerce.get("currency") or "INR",
                # Catalogue stock null means commerce truth is unsynced; seed zero.
                "stock_quantity": variant.get("stock") or 0,
                "is_active": bool(variant.get("is_active", True)),
            })

        images = product.get("images") or {}
        if images.get("paths_verified"):
            position = 0
            if images.get("primary"):
                image_rows.append({
                    "product_id": product_row_id, "url": images["primary"],
                    "alt_text": images.get("alt") or product["name"],
                    "image_type": "PRIMARY", "position": position, "is_primary": True,
                })
                position += 1
            for image_type, paths in (("GALLERY", images.get("gallery")),
                                      ("LIFESTYLE", images.get("lifestyle")),
                                      ("DETAIL", images.get("detail"))):
                for url in paths or []:
                    image_rows.append({
                        "product_id": product_row_id, "url": url,
                        "alt_text": images.get("alt") or product["name"],
                        "image_type": image_type, "position": position, "is_primary": False,
                    })
                    position += 1

    child_list = sorted(child_categories.values(), key=lambda row: row["slug"])
    return {
        "categories": list(parent_categories.values()) + child_list,
        "products": product_rows,
        "shades": shade_rows,
        "variants": variant_rows,
        "images": image_rows,
    }


def upsert_sql(table: str, columns: list[str], conflict: list[str]) -> str:
    placeholders = ", ".join(f"%({column})s" for column in columns)
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in columns if column not in ("id", *conflict)
    )
    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    if updates:
        statement += f" ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {updates}, updated_at = NOW()"
    else:
        statement += f" ON CONFLICT ({', '.join(conflict)}) DO NOTHING"
    return statement


CATEGORY_COLUMNS = ["id", "name", "slug", "parent_id", "sort_order"]
PRODUCT_COLUMNS = ["id", "category_id", "name", "slug", "product_type", "short_description",
                   "description", "directions", "benefits", "status", "launch_date"]
SHADE_COLUMNS = ["id", "product_id", "name", "slug", "code", "hex", "undertone"]
VARIANT_COLUMNS = ["id", "product_id", "shade_id", "name", "sku", "size", "price",
                   "compare_at_price", "currency", "stock_quantity", "is_active"]
IMAGE_COLUMNS = ["product_id", "url", "alt_text", "image_type", "position", "is_primary"]


def connect(dsn: str):
    try:
        import psycopg
    except ImportError:
        raise SystemExit('psycopg is required: pip install "psycopg[binary]"')
    return psycopg.connect(dsn)


def import_rows(cursor: Any, rows: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    parents = [row for row in rows["categories"] if row["parent_id"] is None]
    children = [row for row in rows["categories"] if row["parent_id"] is not None]
    cursor.executemany(upsert_sql("categories", CATEGORY_COLUMNS, ["slug"]), parents)
    cursor.executemany(upsert_sql("categories", CATEGORY_COLUMNS, ["slug"]), children)

    from psycopg.types.json import Jsonb
    product_params = [
        {**row, "benefits": Jsonb(row["benefits"])} for row in rows["products"]
    ]
    cursor.executemany(upsert_sql("products", PRODUCT_COLUMNS, ["slug"]), product_params)

    cursor.executemany(upsert_sql("shades", SHADE_COLUMNS, ["product_id", "slug"]), rows["shades"])
    cursor.executemany(upsert_sql("product_variants", VARIANT_COLUMNS, ["sku"]), rows["variants"])

    # product_images has no natural unique key; replace per imported product instead.
    product_ids = [row["id"] for row in rows["products"]]
    cursor.execute("DELETE FROM product_images WHERE product_id = ANY(%s)", (product_ids,))
    cursor.executemany(
        "INSERT INTO product_images ({columns}) VALUES ({placeholders})".format(
            columns=", ".join(IMAGE_COLUMNS),
            placeholders=", ".join(f"%({column})s" for column in IMAGE_COLUMNS),
        ),
        rows["images"],
    )

    counts = {name: len(values) for name, values in rows.items()}
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import the YAFA VANAM catalogue into PostgreSQL.")
    parser.add_argument("--catalogue", default=str(DEFAULT_CATALOGUE), help="normalized catalogue JSON")
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"), help="PostgreSQL DSN (default $DATABASE_URL)")
    parser.add_argument("--dry-run", action="store_true", help="validate and project rows without touching the database")
    parser.add_argument("--force", action="store_true", help="import even when validation reports errors")
    args = parser.parse_args(argv)

    catalogue_path = Path(args.catalogue)
    try:
        with catalogue_path.open("r", encoding="utf-8") as handle:
            products = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read catalogue {catalogue_path}: {exc}")

    findings = validate_catalogue(products)
    errors = [f for f in findings if f.severity == "error"]
    for finding in findings:
        print(f"[{finding.severity.upper()}] {finding.location}: {finding.message}")
    if errors and not args.force:
        raise SystemExit(f"{len(errors)} validation error(s); fix them or pass --force")

    if not isinstance(products, list) or not products:
        raise SystemExit("catalogue must be a non-empty JSON array")
    rows = build_rows(products)
    print(f"projected: {len(rows['categories'])} categories, {len(rows['products'])} products, "
          f"{len(rows['shades'])} shades, {len(rows['variants'])} variants, {len(rows['images'])} images")

    if args.dry_run:
        print("dry run complete; no database changes made")
        return 0

    if not args.dsn:
        raise SystemExit("no DSN: pass --dsn or set DATABASE_URL")

    with connect(args.dsn) as connection:
        with connection.cursor() as cursor:
            counts = import_rows(cursor, rows)
        connection.commit()
    print(f"imported: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
