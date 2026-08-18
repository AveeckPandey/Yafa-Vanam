from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def _default_catalogue_path() -> Path:
    # service/app/advisor/catalogue.py -> repo root/data/processed/Product.json
    return Path(__file__).resolve().parents[4] / "data" / "processed" / "Product.json"


@lru_cache(maxsize=1)
def load_catalogue() -> list[dict[str, Any]]:
    path = Path(os.getenv("YAFA_CATALOGUE_PATH", str(_default_catalogue_path())))
    with path.open("r", encoding="utf-8") as handle:
        products = json.load(handle)
    if not isinstance(products, list):
        raise ValueError("YAFA catalogue must be a JSON array")
    return products


def active_products() -> list[dict[str, Any]]:
    return [p for p in load_catalogue() if p.get("status") == "active"]


def product_by_id(product_id: str) -> dict[str, Any] | None:
    return next((p for p in load_catalogue() if p.get("id") == product_id), None)


def product_by_slug(slug: str) -> dict[str, Any] | None:
    return next((p for p in load_catalogue() if p.get("slug") == slug), None)


def variant_is_available(variant: dict[str, Any]) -> bool:
    # null stock in the catalogue means commerce truth has not been synced.
    # Do not interpret null as out-of-stock; Go must validate sellability.
    return bool(variant.get("is_active", True))
