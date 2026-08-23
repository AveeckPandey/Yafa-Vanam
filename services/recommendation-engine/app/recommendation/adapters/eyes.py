"""eyes.json adapter: per-type buckets, brow rules, eye-colour rules, palettes.

Palette products (Eyeshadow quads, Eye Sets) carry their pans in
palette_colors[] and exactly one sellable variant — they must never be fanned
out per pan (enforced structurally in candidate_filter.select).
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters.base import BaseAdapter
from app.recommendation.canonical.normalization import REGISTRY


class EyesAdapter(BaseAdapter):
    category = "eyes"
    filename = "eyes.json"

    def observe_vocabulary(self) -> None:
        families = {
            (profile.get("color_profile") or {}).get("color_family")
            for system in self.shared_systems.values()
            for profile in system.get("profiles", {}).values()
        }
        REGISTRY.observe("eyes", "color_family", {family for family in families if family})
        REGISTRY.observe("eyes", "eye_colour", self.eye_colour_matching()["rules"].keys())

    @property
    def shared_systems(self) -> dict[str, dict[str, Any]]:
        return self.document["shared_shade_systems"]

    def by_type(self) -> dict[str, list[dict[str, Any]]]:
        """Products bucketed by product_type (mascara/brows/eyeliner/eyeshadow/eye sets)."""
        buckets: dict[str, list[dict[str, Any]]] = {}
        for product in self.products():
            buckets.setdefault(product.get("product_type", "unknown"), []).append(product)
        return buckets

    def palettes(self) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
        """(product, palette_colors[]) for every pan-based product."""
        return [
            (product, product.get("palette_colors") or [])
            for product in self.products()
            if product.get("palette_colors")
        ]

    def shade_profiles_for_variant(self, variant: dict[str, Any]) -> dict[str, Any] | None:
        """Join a variant to its shared-shade profile via eye_recommendation ref."""
        link = variant.get("eye_recommendation") or {}
        ref = link.get("recommendation_profile_ref") or ""
        system_id, _, slug = ref.partition(":")
        return (self.shared_systems.get(system_id, {}).get("profiles") or {}).get(slug)

    def shade_profiles_for_product(self, product_id: str) -> list[dict[str, Any]]:
        """Per-shade colour profiles of one product's sellable shades.

        Palette products contribute their palette_colors[] pans here — colour
        data without ever fanning pans out as sellable variants.
        """
        product = self.find(product_id)
        if product and product.get("palette_colors"):
            return list(product["palette_colors"])
        profiles: list[dict[str, Any]] = []
        for variant in (product or {}).get("variants", []):
            profile = self.shade_profiles_for_variant(variant)
            if profile:
                profiles.append(profile)
        return profiles

    def shared_profiles(self, system_id: str) -> dict[str, dict[str, Any]]:
        return self.shared_systems.get(system_id, {}).get("profiles", {})

    def eye_colour_matching(self) -> dict[str, Any]:
        return self.document["eye_colour_matching"]

    def eye_colour_rules(self, eye_colour: str | None) -> dict[str, Any] | None:
        """{boost[], secondary[], reason} for a colour — boosts only, never gates."""
        from app.recommendation.canonical.normalization import normalize_token

        if not eye_colour:
            return None
        return self.eye_colour_matching()["rules"].get(normalize_token(eye_colour))

    def brow_matching(self) -> dict[str, Any]:
        return self.document["brow_matching"]

    def brow_rules(self) -> list[dict[str, Any]]:
        """Ordered brow_matching.rules rows: hair_depth[] x hair_temperature -> recommended[]."""
        return self.brow_matching().get("rules") or []

    def category_rules(self) -> dict[str, Any]:
        """eye_recommendation_rules incl. ranking_order/weights/category_specific."""
        return self.document["eye_recommendation_rules"]

    def weights_table(self) -> dict[str, float]:
        return self.category_rules()["weights"]

    def outfit_families(self) -> dict[str, Any]:
        return (self.document.get("outfit_harmony") or {}).get("families") or {}

    def look_styles(self) -> dict[str, Any]:
        return self.document.get("look_styles") or {}

    def palette_coordination_rules(self) -> list[dict[str, Any]]:
        return self.document.get("palette_coordination_rules") or []
