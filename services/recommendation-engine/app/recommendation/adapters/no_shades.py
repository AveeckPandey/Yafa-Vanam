"""no_shades.json adapter: skincare, fragrance, compatibility rules, routine.

compatibility.rules[] are CONCEPT-keyed (ingredient concepts like
hyaluronic_acid via indexes.active_ingredient_concepts), never product-id
equality; every rule carries requires_formula_confirmation=True so any firing
must surface as a warning, not a claim.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters.base import BaseAdapter


class NoShadesAdapter(BaseAdapter):
    category = "no_shades"
    filename = "no_shades.json"

    def observe_vocabulary(self) -> None:
        from app.recommendation.canonical.normalization import REGISTRY

        REGISTRY.observe("no_shades", "skin_type", self.document["indexes"]["skin_types"])
        REGISTRY.observe("no_shades", "concern", self.document["indexes"]["concerns"])
        REGISTRY.observe("no_shades", "goal", self.document["indexes"]["goals"])
        REGISTRY.observe("no_shades", "routine_step", self.document["indexes"]["routine_steps"])

    @property
    def skincare_engine(self) -> dict[str, Any]:
        return self.document["skincare_recommendation_engine"]

    def weights_table(self) -> dict[str, Any]:
        return self.skincare_engine["weights"]

    def ranking_order(self) -> list[str]:
        return self.skincare_engine.get("ranking_order") or []

    def routine_builder(self) -> dict[str, Any]:
        return self.skincare_engine.get("routine_builder") or {}

    def indexes(self) -> dict[str, Any]:
        return self.document["indexes"]

    def skincare_candidates(self) -> list[dict[str, Any]]:
        """Skincare-relevant products: no fragrance profile, not primer/setting spray."""
        return [
            product for product in self.products()
            if not product.get("fragrance_profile")
            and product.get("product_type") not in {"Face Primer", "Setting Spray"}
        ]

    def fragrances(self) -> list[dict[str, Any]]:
        return [product for product in self.products() if product.get("fragrance_profile")]

    def compatibility_rules(self, product_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """{product_id: [rule,...]} — or one product's rules when id given."""
        if product_id:
            return {product_id: ((self.find(product_id) or {}).get("compatibility") or {}).get("rules") or []}
        rules: dict[str, list[dict[str, Any]]] = {}
        for product in self.products():
            product_rules = (product.get("compatibility") or {}).get("rules") or []
            if product_rules:
                rules[product["id"]] = product_rules
        return rules

    def fragrance_recommendation_engine(self) -> dict[str, Any]:
        return self.document.get("fragrance_recommendation_engine") or {}
