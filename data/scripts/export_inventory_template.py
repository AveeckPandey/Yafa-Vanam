"""Generate a reviewable inventory CSV from the canonical product catalogue."""

from __future__ import annotations

import csv
import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "data" / "processed" / "Product.json"
OUTPUT = ROOT / "data" / "inventory" / "initial-stock.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--default-on-hand",
        type=int,
        default=0,
        help="Quantity assigned to every active variant (default: 0).",
    )
    parser.add_argument(
        "--reason",
        default="initial warehouse count required",
        help="Audit reason written to every CSV row.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help=f"Destination CSV (default: {OUTPUT}).",
    )
    args = parser.parse_args()
    if args.default_on_hand < 0:
        parser.error("--default-on-hand must be zero or greater")
    return args


def main() -> None:
    args = parse_args()
    products = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for product in products:
        if product.get("status") != "active":
            continue
        for variant in product.get("variants", []):
            if not variant.get("is_active", False):
                continue
            rows.append(
                {
                    "variant_id": variant["id"],
                    "sku": variant.get("sku") or "",
                    "product_name": product["name"],
                    "option": variant.get("size") or (variant.get("shade") or {}).get("name") or "Default",
                    "on_hand_quantity": args.default_on_hand,
                    "low_stock_threshold": 10,
                    "reason": args.reason,
                }
            )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} active variants to {output}")


if __name__ == "__main__":
    main()
