"""Canonical pydantic models: profile in, recommendations out (spec §4/§5).

Every profile field is optional — engines branch on presence and the scorer's
denominator-shrinking normalization guarantees missing inputs never invent
scores. `raw` retains the original payload for provenance/debug only.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.recommendation.canonical.enums import MatchClass, ShadeAxis


class CanonicalProfile(BaseModel):
    """Typed mirror of v1.normalise_profile output, field-for-field."""

    shade_code: str | None = None
    shade_confirmed: bool = False
    depth: str | None = None
    undertone: str | None = None
    lab: dict[str, float] | None = None
    capture_confidence: float | None = None
    skin_types: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    sensitivity: str | None = None
    eye_colour: str | None = None
    hair_colour: str | None = None
    hair_depth: str | None = None
    hair_temperature: str | None = None
    coverage: str | None = None
    finish: str | None = None
    style: str | None = None
    lip_finish: str | None = None
    eye_intensity: str | None = None
    cheek_finish: str | None = None
    occasion: str | None = None
    daypart: str | None = None
    season: str | None = None
    outfit: dict[str, Any] | None = None
    fragrance: dict[str, Any] | None = None
    safety_conditions: set[str] = Field(default_factory=set)
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceRef(BaseModel):
    file: str


class Recommendation(BaseModel):
    """Public output row (§5 superset): ids + score + machine-readable why."""

    product_id: str
    product_name: str | None = None
    product_type: str | None = None
    variant_id: str | None = None
    category: str
    score: float  # 0..1 rounded to 3 dp at the boundary only
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source: SourceRef
    color_family: str | None = None  # M3 coordination input
    shade_name: str | None = None
    shade_hex: str | None = None
    score_breakdown: dict[str, float] | None = None  # debug mode only


class ShadeMatch(BaseModel):
    code: str
    name: str | None = None
    hex: str | None = None
    depth_index: int
    undertone_axis: ShadeAxis | None = None
    delta_e00: float | None = None
    match_class: MatchClass
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    product_id: str
    variant_id: str
    source: SourceRef


class CoordinationHints(BaseModel):
    """M3/M4 seam: cross-category context an engine may consume.

    Built NOW so engines have one stable signature; M3 flips the cheek
    lip_coordination factor from inert to active without touching callers.
    """

    lip_color_family: str | None = None
    liner_pairing_requested: bool = False
    look_style: str | None = None


class EngineResult(BaseModel):
    category: str
    items: list[Recommendation] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)  # e.g. application_intensity


class Candidate:
    """Filter/scorer unit: one sellable product (palettes stay ONE candidate)."""

    __slots__ = ("product", "variants", "shade_profiles", "source_file", "warnings")

    def __init__(
        self,
        product: dict[str, Any],
        variants: list[dict[str, Any]],
        source_file: str,
        shade_profiles: list[dict[str, Any]] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.product = product
        self.variants = variants  # empty list means "product-level candidate"
        self.source_file = source_file
        self.shade_profiles = shade_profiles or []
        self.warnings = warnings or []

    @property
    def product_id(self) -> str:
        return self.product["id"]

    def primary_variant(self) -> dict[str, Any] | None:
        return self.variants[0] if self.variants else None
