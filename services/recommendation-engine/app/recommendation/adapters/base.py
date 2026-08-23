"""Dataset adapter base: load-once access to one authoritative dataset file.

Service copies under services/recommendation-engine/data/ are authoritative
for the engine (byte-identical to the repo-root data/processed/ copies; those
belong to the RAG ingestion area). Structural problems raise — mirroring
v1.sources() strictness — while vocabulary surprises only warn via REGISTRY.
"""
from __future__ import annotations

from typing import Any, ClassVar

from app.recommendation.canonical.normalization import REGISTRY


class BaseAdapter:
    category: ClassVar[str]
    filename: ClassVar[str]

    def __init__(self, document: dict[str, Any]) -> None:
        if not isinstance(document, dict) or not isinstance(document.get("products"), list):
            raise RuntimeError(f"Dataset {self.filename} must be an object containing a products array")
        for product in document["products"]:
            if not isinstance(product, dict) or not product.get("id") or not product.get("name"):
                raise RuntimeError(f"Dataset {self.filename} has a product without id or name")
        self._document = document
        self._products: list[dict[str, Any]] = document["products"]
        self._by_id: dict[str, dict[str, Any]] = {product["id"]: product for product in self._products}
        self.observe_vocabulary()

    # -- required hooks -------------------------------------------------
    def observe_vocabulary(self) -> None:
        """Register this dataset's enum-ish values with REGISTRY (warn-only drift)."""

    # -- shared surface --------------------------------------------------
    @property
    def document(self) -> dict[str, Any]:
        return self._document

    def products(self) -> list[dict[str, Any]]:
        return self._products

    def find(self, product_id: str) -> dict[str, Any] | None:
        return self._by_id.get(product_id)

    def active(self) -> list[dict[str, Any]]:
        return [product for product in self._products if product.get("status") in {"active", None}]

    @staticmethod
    def recommendation_profile(product: dict[str, Any]) -> dict[str, Any]:
        return product.get("recommendation_profile") or {}
