"""lips.json adapter: per-shade profiles via recommendation_profile_ref joins."""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters.base import BaseAdapter
from app.recommendation.canonical.normalization import REGISTRY, normalize_token


class LipsAdapter(BaseAdapter):
    category = "lips"
    filename = "lips.json"

    def observe_vocabulary(self) -> None:
        families: set[str] = set()
        for profile in self._all_shade_profiles():
            family = (profile.get("color_profile") or {}).get("color_family")
            if family:
                families.add(family)
        REGISTRY.observe("lips", "color_family", families)

    def colour_products(self) -> list[dict[str, Any]]:
        return [product for product in self.products() if product.get("product_type") != "Lip Liner"]

    def liners(self) -> list[dict[str, Any]]:
        return [product for product in self.products() if product.get("product_type") == "Lip Liner"]

    @property
    def shade_systems(self) -> dict[str, dict[str, Any]]:
        return self.document["shade_systems"]

    def _all_shade_profiles(self) -> list[dict[str, Any]]:
        profiles: list[dict[str, Any]] = []
        for system in self.shade_systems.values():
            profiles.extend(system.get("profiles", {}).values())
        return profiles

    def shade_profiles_for_product(self, product_id: str) -> list[dict[str, Any]]:
        """Ordered shade profiles of one product, joined from its variants.

        Variants carry `shade.recommendation_profile_ref` ("<system>:<slug>").
        """
        system = self.shade_systems.get(product_id, {})
        profiles = system.get("profiles", {})
        joined: list[dict[str, Any]] = []
        product = self.find(product_id)
        for variant in (product or {}).get("variants", []):
            ref = ((variant.get("shade") or {}).get("recommendation_profile_ref")) or ""
            _, _, slug = ref.partition(":")
            if slug and slug in profiles:
                joined.append(profiles[slug])
            elif not ref and profiles:
                # Products whose variants predate the ref join fall back to
                # positional order within their own shade system.
                joined.extend(profiles.values())
                break
        return joined

    def recommendation_rules(self) -> dict[str, Any]:
        return self.document["lip_recommendation_rules"]

    def weights_table(self) -> dict[str, float]:
        return self.recommendation_rules()["weights"]

    def liner_pairing(self) -> dict[str, Any]:
        return self.document.get("lip_liner_pairing") or {}

    def outfit_families(self) -> dict[str, Any]:
        """Grouped harmony table: {neutral_outfits: {examples[], recommended_lip_families[], ...}, ...}."""
        return self.document.get("outfit_harmony") or {}

    def look_styles(self) -> dict[str, Any]:
        return self.document.get("look_styles") or {}
