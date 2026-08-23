"""cheeks.json adapter: shared blush systems + product format profiles.

NOTE: the top-level outfit_harmony.families table is EMPTY in this dataset —
the outfit signal lives on each shared-shade profile's
recommendation.outfit_colour_families. Engines must go through
shared_profiles(), never the grouped table.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters.base import BaseAdapter


class CheeksAdapter(BaseAdapter):
    category = "cheeks"
    filename = "cheeks.json"

    def observe_vocabulary(self) -> None:
        from app.recommendation.canonical.normalization import REGISTRY

        families = {
            (profile.get("color_profile") or {}).get("color_family")
            for system in self.shared_systems.values()
            for profile in system.get("profiles", {}).values()
        }
        REGISTRY.observe("cheeks", "color_family", {family for family in families if family})

    @property
    def shared_systems(self) -> dict[str, dict[str, Any]]:
        return self.document["shared_shade_systems"]

    def blushes(self) -> list[dict[str, Any]]:
        # Every product in cheeks.json is a cheek product (Blush / Lip + Cheek).
        return list(self.products())

    def shade_profiles_for_product(self, product_id: str) -> list[dict[str, Any]]:
        """Shade profiles joined via variant.shade.recommendation_profile_ref ("<system>:<slug>")."""
        joined: list[dict[str, Any]] = []
        product = self.find(product_id)
        for variant in (product or {}).get("variants", []):
            ref = ((variant.get("shade") or {}).get("recommendation_profile_ref")) or ""
            system_id, _, slug = ref.partition(":")
            profile = (self.shared_systems.get(system_id, {}).get("profiles") or {}).get(slug)
            if profile:
                joined.append(profile)
        return joined

    def shared_profiles(self, system_id: str | None = None) -> dict[str, dict[str, Any]]:
        """Profiles of one shared system, or every profile across all systems."""
        if system_id:
            return self.shared_systems.get(system_id, {}).get("profiles", {})
        all_profiles: dict[str, dict[str, Any]] = {}
        for system in self.shared_systems.values():
            all_profiles.update(system.get("profiles", {}))
        return all_profiles

    def format_profiles(self) -> dict[str, Any]:
        """product_format_profiles keyed by product id — the FORMULA-stage input."""
        return self.document.get("product_format_profiles") or {}

    def recommendation_rules(self) -> dict[str, Any]:
        return self.document["cheek_recommendation_rules"]

    def weights_table(self) -> dict[str, float]:
        return self.recommendation_rules()["weights"]

    def depth_application_rules(self) -> dict[str, str]:
        return self.recommendation_rules().get("depth_application_rules") or {}

    def lip_coordination(self) -> dict[str, Any]:
        return self.document.get("cross_category_lip_coordination") or {}

    def look_styles(self) -> dict[str, Any]:
        return self.document.get("look_styles") or {}

    def outfit_families(self) -> dict[str, Any]:
        # Deliberately returns whatever exists; currently empty. Per-shade
        # lists are authoritative for cheeks.
        return (self.document.get("outfit_harmony") or {}).get("families") or {}
