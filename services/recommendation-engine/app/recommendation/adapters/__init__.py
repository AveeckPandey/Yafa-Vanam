"""Adapter registry: one cached adapter per authoritative dataset file.

load_all() enforces the catalogue invariant (78 products, unique ids across
datasets) that v1.sources() established. clear_caches() exists for tests —
adapters are lru_cached, so dataset edits during a session are invisible
until cleared (tests mutate copies, never files).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.recommendation.adapters.base import BaseAdapter
from app.recommendation.adapters.cheeks import CheeksAdapter
from app.recommendation.adapters.eyes import EyesAdapter
from app.recommendation.adapters.lips import LipsAdapter
from app.recommendation.adapters.no_shades import NoShadesAdapter
from app.recommendation.adapters.skin import SkinAdapter

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
EXPECTED_TOTAL_PRODUCTS = 78

_ADAPTER_TYPES: dict[str, type[BaseAdapter]] = {
    SkinAdapter.category: SkinAdapter,
    LipsAdapter.category: LipsAdapter,
    CheeksAdapter.category: CheeksAdapter,
    EyesAdapter.category: EyesAdapter,
    NoShadesAdapter.category: NoShadesAdapter,
}

EXPECTED_COUNTS = {"skin": 11, "lips": 8, "cheeks": 6, "eyes": 15, "no_shades": 38}


def _load_document(filename: str) -> dict:
    path = DATA_DIR / filename
    if not path.exists():
        raise RuntimeError(f"Required recommendation dataset is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Malformed recommendation dataset {filename}: {error}") from error
    return document


@lru_cache(maxsize=None)
def get_adapter(category: str) -> BaseAdapter:
    """Build (once) the adapter for a category: skin|lips|cheeks|eyes|no_shades."""
    adapter_type = _ADAPTER_TYPES.get(category)
    if adapter_type is None:
        raise KeyError(f"Unknown recommendation category {category!r}")
    return adapter_type(_load_document(adapter_type.filename))


def load_all() -> dict[str, BaseAdapter]:
    """All five adapters, asserting per-file counts and the 78-product invariant."""
    adapters = {category: get_adapter(category) for category in _ADAPTER_TYPES}
    for category, expected in EXPECTED_COUNTS.items():
        found = len(adapters[category].products())
        if found != expected:
            raise RuntimeError(f"Dataset {category}.json has {found} products, expected {expected}")
    all_ids = [product["id"] for adapter in adapters.values() for product in adapter.products()]
    if len(all_ids) != EXPECTED_TOTAL_PRODUCTS:
        raise RuntimeError(f"Expected {EXPECTED_TOTAL_PRODUCTS} YAFA VANAM products, found {len(all_ids)}")
    if len(set(all_ids)) != len(all_ids):
        duplicates = sorted({product_id for product_id in all_ids if all_ids.count(product_id) > 1})
        raise RuntimeError(f"Duplicate catalogue product IDs: {duplicates}")
    return adapters


def clear_caches() -> None:
    get_adapter.cache_clear()


__all__ = [
    "BaseAdapter",
    "CheeksAdapter",
    "EyesAdapter",
    "LipsAdapter",
    "NoShadesAdapter",
    "SkinAdapter",
    "clear_caches",
    "get_adapter",
    "load_all",
]
