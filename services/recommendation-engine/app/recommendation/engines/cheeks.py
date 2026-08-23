"""Cheeks engine: per-shade scoring + depth-tiered application guidance.

Outfit harmony reads the PER-SHADE recommendation.outfit_colour_families
lists (the grouped top-level table is empty in this dataset). Depth drives
application-intensity notes — a ranking signal, never eligibility.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters import get_adapter
from app.recommendation.candidate_filter import select
from app.recommendation.canonical.normalization import (
    canonical_occasion,
    family_matches,
    normalize_token,
)
from app.recommendation.canonical.schemas import (
    Candidate,
    CanonicalProfile,
    CoordinationHints,
    EngineResult,
    Recommendation,
)
from app.recommendation.engines.base import (
    color_family_of,
    desired_color_family,
    make_recommendation,
    occasion_tags_overlap,
    outfit_colour,
    raw_requested_ids,
    recommendation_block,
    style_matches,
    variant_shade_pairs,
)
from app.recommendation.ranker import rank
from app.recommendation.reason_codes import (
    COMPLEXION_DEPTH_INTENSITY_TUNED,
    REQUESTED_FINISH_OR_PRODUCT_MATCH,
    desired_color_family as desired_color_family_code,
    lip_coordination,
    look_style_priority,
    occasion_match,
    outfit_harmony,
    undertone_match,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import CHEEK_WEIGHTS, effective_weights

# depth band -> depth_application_rules tier key
DEPTH_TIERS: dict[str, str] = {
    "fair": "fair_light",
    "light": "fair_light",
    "light_medium": "light_medium_medium",
    "medium": "light_medium_medium",
    "medium_tan": "medium_tan_tan",
    "tan": "medium_tan_tan",
    "deep": "deep_very_deep",
    "very_deep": "deep_very_deep",
}


def _outfit_recommended_families(shade_profile: dict[str, Any] | None, colour: str | None) -> bool:
    """Per-shade outfit list membership — the authoritative cheek signal."""
    if not colour:
        return False
    listed = {normalize_token(f) for f in recommendation_block(shade_profile).get("outfit_colour_families") or []}
    return colour in listed


def score_shade(
    acc: FactorAccumulator,
    candidate: Candidate,
    profile: CanonicalProfile,
    shade_profile: dict[str, Any] | None,
    *,
    coordination: CoordinationHints | None,
    requested_ids: set[str],
    format_profile: dict[str, Any] | None,
) -> None:
    product = candidate.product
    rec = recommendation_block(shade_profile)
    family = color_family_of(shade_profile)

    if product["id"] in requested_ids:
        acc.credit("user_requested_product_format_or_finish", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)
    elif profile.cheek_finish and format_profile:
        finish = normalize_token(format_profile.get("finish"))
        if finish and finish == normalize_token(profile.cheek_finish):
            acc.credit("user_requested_product_format_or_finish", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)

    wanted_family = desired_color_family(profile)
    if wanted_family and family_matches(family, wanted_family):
        acc.credit("desired_color_family", True, desired_color_family_code(wanted_family))

    depth = normalize_token(profile.depth)
    compatible_depths = {normalize_token(d) for d in rec.get("complexion_depth_compatibility") or []}
    if depth and depth in compatible_depths:
        # Both signals ride one dataset concept; intensity tuning is the note.
        acc.credit("complexion_depth_intensity_fit", True, COMPLEXION_DEPTH_INTENSITY_TUNED)

    undertone = normalize_token(profile.undertone)
    compatible_undertones = {normalize_token(u) for u in rec.get("undertone_compatibility") or []}
    if undertone and undertone in compatible_undertones:
        acc.credit("undertone_compatibility", True, undertone_match(profile.undertone))

    style_codes: list[str] = []
    occasion_hit = canonical_occasion(profile.occasion) and occasion_tags_overlap(
        canonical_occasion(profile.occasion), rec.get("occasion_tags")
    )
    style_hit = style_matches(profile.style, rec.get("look_styles"))
    if style_hit:
        style_codes.append(look_style_priority(profile.style))
    if occasion_hit:
        style_codes.append(occasion_match(canonical_occasion(profile.occasion)))
    if style_codes:
        acc.credit("occasion_and_look_style", True, *style_codes)

    colour = outfit_colour(profile)
    if _outfit_recommended_families(shade_profile, colour):
        acc.credit("outfit_harmony", True, outfit_harmony(colour))

    lip_family = coordination.lip_color_family if coordination else None
    if lip_family:
        recommended_lips = {normalize_token(f) for f in rec.get("recommended_lip_color_families") or []}
        if any(family_matches(lip_family, f) for f in recommended_lips):
            acc.credit(
                "lip_coordination_if_requested",
                True,
                *(lip_coordination(f) for f in rec.get("recommended_lip_color_families") or []),
            )


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("cheeks")
    weights = effective_weights("cheeks", adapter.weights_table(), CHEEK_WEIGHTS)
    requested_ids = raw_requested_ids(profile)
    format_profiles = adapter.format_profiles()

    scored: list[Recommendation] = []
    for candidate in select(adapter, profile):
        best: tuple[float, dict[str, float], list[str], dict[str, Any] | None, dict[str, Any] | None] | None = None
        for variant, shade_profile in variant_shade_pairs(candidate):
            acc = FactorAccumulator(weights)
            score_shade(
                acc, candidate, profile, shade_profile,
                coordination=coordination,
                requested_ids=requested_ids,
                format_profile=format_profiles.get(candidate.product_id),
            )
            score, breakdown = acc.finalize_makeup()
            acc.baseline()
            if best is None or score > best[0]:
                best = (score, breakdown, list(acc.reason_codes), variant, shade_profile)
        assert best is not None
        score, breakdown, codes, variant, shade_profile = best
        scored.append(make_recommendation(
            candidate,
            category="cheeks",
            score=score,
            reason_codes=codes,
            warnings=list(candidate.warnings),
            variant=variant,
            shade_profile=shade_profile,
            breakdown=breakdown if debug else None,
        ))

    notes: dict[str, Any] = {}
    tier = DEPTH_TIERS.get(normalize_token(profile.depth) or "", "")
    guidance = adapter.depth_application_rules().get(tier)
    if guidance:
        notes["application_intensity"] = guidance
    return EngineResult(category="cheeks", items=rank(scored, limit=limit), notes=notes)
