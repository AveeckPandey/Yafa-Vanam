"""Shared engine plumbing: Recommendation assembly and small lookup helpers.

Every engine keeps its factor logic local (the inputs are structurally
different) but builds output rows through make_recommendation() so the public
shape stays identical across categories.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.canonical.normalization import canonical_occasion, normalize_token
from app.recommendation.canonical.schemas import (
    Candidate,
    Recommendation,
    SourceRef,
)

# Dataset occasion_tags use raw marketing tokens ("brunch", "date_night",
# "wedding"); profiles carry the canonical trio. This groups the tag space —
# presentation-layer only, never an eligibility gate.
OCCASION_TAG_CLASSES: dict[str, frozenset[str]] = {
    "daily": frozenset({"daily", "everyday", "work", "office", "brunch", "school"}),
    "evening": frozenset({"evening", "date_night", "night_out", "party", "dinner"}),
    "special_occasion": frozenset({"special_occasion", "wedding", "bridal", "formal"}),
}


def occasion_tags_overlap(canonical: str | None, tags: list[str] | None) -> bool:
    """True when a profile's canonical occasion meets a shade's raw tags."""
    if not canonical:
        return False
    wanted = OCCASION_TAG_CLASSES.get(canonical, frozenset({canonical}))
    tag_tokens = {canonical_occasion(normalize_token(tag)) or normalize_token(tag) for tag in tags or []}
    return bool(wanted & tag_tokens)


def style_matches(style: str | None, style_tags: list[str] | None) -> bool:
    """Normalized comparison absorbing the hyphen/underscore drift between datasets."""
    if not style:
        return False
    wanted = normalize_token(style)
    return any(normalize_token(tag) == wanted for tag in style_tags or [])


def outfit_colour(profile: Any) -> str | None:
    """The user's outfit colour token, mirroring v1's lookup order."""
    outfit = profile.outfit or {}
    colour = outfit.get("primary_colour") or outfit.get("primary_color")
    if not colour:
        dominant = outfit.get("dominant_colors") or []
        colour = dominant[0] if dominant else None
    return normalize_token(colour) if colour else None


def raw_requested_ids(profile: Any) -> set[str]:
    """Product ids the user explicitly asked for (raw payload passthrough)."""
    ids = profile.raw.get("requested_product_ids") or []
    return {str(value) for value in ids}


def desired_color_family(profile: Any) -> str | None:
    desired = profile.raw.get("desired_color_family")
    if not desired:
        prefs = profile.raw.get("makeup_preferences") or {}
        desired = prefs.get("color_family")
    return normalize_token(desired) if desired else None


def shade_of(variant: dict[str, Any] | None) -> dict[str, Any]:
    return ((variant or {}).get("shade") or {})


def color_family_of(shade_profile: dict[str, Any] | None) -> str | None:
    family = ((shade_profile or {}).get("color_profile") or {}).get("color_family")
    return normalize_token(family) if family else None


def recommendation_block(shade_profile: dict[str, Any] | None) -> dict[str, Any]:
    return (shade_profile or {}).get("recommendation") or {}


def normalized_key_lookup(mapping: dict[str, Any], key: str | None) -> Any:
    """Dataset keys drift between hyphens and underscores (eyes look_styles);
    resolve by normalized comparison instead of trusting either spelling."""
    if key is None:
        return None
    wanted = normalize_token(key)
    for map_key, value in mapping.items():
        if normalize_token(map_key) == wanted:
            return value
    return None


def make_recommendation(
    candidate: Candidate,
    *,
    category: str,
    score: float,
    reason_codes: list[str],
    warnings: list[str],
    variant: dict[str, Any] | None = None,
    shade_profile: dict[str, Any] | None = None,
    breakdown: dict[str, float] | None = None,
) -> Recommendation:
    """One public row from a scored candidate + winning variant/shade."""
    shade = shade_of(variant)
    family = color_family_of(shade_profile)
    profile = shade_profile or {}
    name = shade.get("name") or profile.get("name")
    hex_value = shade.get("hex") or profile.get("hex")
    return Recommendation(
        product_id=candidate.product_id,
        product_name=candidate.product.get("name"),
        product_type=candidate.product.get("product_type"),
        variant_id=(variant or {}).get("id"),
        category=category,
        score=round(max(0.0, min(1.0, score)), 3),
        reason_codes=reason_codes,
        warnings=list(warnings),
        source=SourceRef(file=candidate.source_file),
        color_family=family,
        shade_name=name,
        shade_hex=hex_value,
        score_breakdown=dict(breakdown) if breakdown else None,
    )


def variant_shade_pairs(candidate: Candidate) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """(variant, joined shade profile) pairs; positional when counts diverge.

    Products without per-shade profiles yield one (variant, None) pair so
    product-level scoring still happens.
    """
    variants = candidate.variants or [None]
    profiles = candidate.shade_profiles
    if not profiles:
        return [(variant, None) for variant in variants]
    pairs: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    for index, variant in enumerate(variants):
        profile = profiles[index] if index < len(profiles) else None
        pairs.append((variant, profile))
    return pairs
