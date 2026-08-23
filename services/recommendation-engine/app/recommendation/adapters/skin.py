"""skin.json adapter: earth_skin_24 shade system + complexion support products."""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters.base import BaseAdapter
from app.recommendation.canonical.normalization import REGISTRY, normalize_token


class SkinAdapter(BaseAdapter):
    category = "skin"
    filename = "skin.json"

    def observe_vocabulary(self) -> None:
        REGISTRY.observe("skin", "depth_family", (shade.get("depth_family") for shade in self.shade_records()))
        REGISTRY.observe("skin", "undertone", (shade.get("undertone") for shade in self.shade_records()))

    @property
    def shade_system(self) -> dict[str, Any]:
        return self.document["shade_systems"]["earth_skin_24"]

    def foundations(self) -> list[dict[str, Any]]:
        exact_types = {"Foundation", "Skin Tint", "Powder Foundation"}
        return [product for product in self.products() if product.get("product_type") in exact_types]

    def support_products(self) -> dict[str, list[dict[str, Any]]]:
        """Non-shade-matching complexion products grouped by recommendation role."""
        roles = {"Concealer": "concealer", "Setting Powder": "powder", "Color Corrector": "corrector",
                 "Bronzer": "bronzer", "Contour": "contour", "Highlighter": "highlighter"}
        grouped: dict[str, list[dict[str, Any]]] = {}
        for product in self.products():
            role = roles.get(product.get("product_type"))
            if role:
                grouped.setdefault(role, []).append(product)
        return grouped

    def shade_records(self) -> list[dict[str, Any]]:
        """The 24 master shades flattened from the shared system."""
        return list(self.shade_system["shades"])

    def matching_engine(self) -> dict[str, Any]:
        return self.document["skin_matching_engine"]

    def delta_e_thresholds(self) -> list[dict[str, Any]]:
        return self.matching_engine()["delta_e00_thresholds"]

    def confidence_anchors(self) -> list[dict[str, Any]]:
        return self.matching_engine()["confidence_model"]["active_model"]["match_score_anchors"]

    def neighbors(self, code: str) -> dict[str, Any]:
        graph = self.matching_engine()["neighbor_graph"]
        return graph.get(code.upper(), {})
