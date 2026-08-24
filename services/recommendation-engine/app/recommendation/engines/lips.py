"""Lips engine: per-shade scoring over joined recommendation profiles.

Every colour-theory input (undertone, depth contrast, outfit, look style) is
a boost inside the weighted normalization — never a gate. The best shade of a
product wins; products are what get ranked.
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
    LIP_LINER_PAIRING_MATCH,
    REQUESTED_FINISH_OR_PRODUCT_MATCH,
    COMPLEXION_DEPTH_CONTRAST_MATCH,
    CHEEK_LIP_FAMILY_COORDINATION,
    desired_color_family as desired_color_family_code,
    look_style_priority,
    occasion_match,
    outfit_harmony,
    undertone_match,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import (
    CHEEK_LIP_COORDINATION_STRENGTH,
    LIP_WEIGHTS,
    effective_weights,
)


def _outfit_recommended_families(adapter: Any, colour: str | None) -> set[str]:
    """Families the dataset's grouped harmony table recommends for an outfit."""
    if not colour:
        return set()
    for _group, table in (adapter.outfit_families() or {}).items():
        examples = {normalize_token(e) for e in table.get("examples") or []}
        if colour in examples:
            return {normalize_token(f) for f in table.get("recommended_lip_families") or []}
    return set()


def _liner_paired_families(adapter: Any) -> set[str]:
    """Families some liner shades pair with (metadata keys like pairing_rule
    are strings, not tables — skip them)."""
    paired: set[str] = set()
    for table in (adapter.liner_pairing() or {}).values():
        if not isinstance(table, dict):
            continue
        paired.update(normalize_token(f) for f in table.get("best_with_families") or [])
    return paired


def score_shade(
    acc: FactorAccumulator,
    candidate: Candidate,
    profile: CanonicalProfile,
    shade_profile: dict[str, Any] | None,
    *,
    coordination: CoordinationHints | None,
    requested_ids: set[str],
    outfit_families: set[str],
    liner_families: set[str],
) -> None:
    product = candidate.product
    rec = recommendation_block(shade_profile)
    family = color_family_of(shade_profile)

    if product["id"] in requested_ids:
        acc.credit("user_requested_product_or_finish", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)
    elif profile.lip_finish and shade_profile:
        finish = normalize_token((shade_profile.get("color_profile") or {}).get("finish"))
        if finish and finish == normalize_token(profile.lip_finish):
            acc.credit("user_requested_product_or_finish", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)

    wanted_family = desired_color_family(profile)
    if wanted_family and family_matches(family, wanted_family):
        acc.credit("desired_color_family", True, desired_color_family_code(wanted_family))

    # Cheek->lip orchestration (spec Phase 2 §11): the orchestrator forwards
    # the selected cheek family; a matching lip family earns a graded boost.
    # Explicit user family requests above always dominate via max().
    coordination_family = (
        normalize_token(coordination.lip_color_family)
        if coordination and coordination.lip_color_family
        else None
    )
    if (
        coordination_family
        and not wanted_family
        and family
        and family_matches(family, coordination_family)
    ):
        acc.credit(
            "desired_color_family",
            CHEEK_LIP_COORDINATION_STRENGTH,
            CHEEK_LIP_FAMILY_COORDINATION,
        )

    depth = normalize_token(profile.depth)
    compatible_depths = {normalize_token(d) for d in rec.get("complexion_depth_compatibility") or []}
    if depth and depth in compatible_depths:
        acc.credit("complexion_depth_as_contrast_signal", True, COMPLEXION_DEPTH_CONTRAST_MATCH)

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

    if outfit_families and any(family_matches(family, f) for f in outfit_families):
        acc.credit("outfit_harmony", True, outfit_harmony(outfit_colour(profile)))

    liner_requested = bool(coordination and coordination.liner_pairing_requested) or bool(
        profile.raw.get("liner_pairing_requested")
    )
    if liner_requested and family and family in liner_families:
        acc.credit("liner_pairing_if_requested", True, LIP_LINER_PAIRING_MATCH)


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("lips")
    weights = effective_weights("lips", adapter.weights_table(), LIP_WEIGHTS)
    requested_ids = raw_requested_ids(profile)
    colour = outfit_colour(profile)
    outfit_families = _outfit_recommended_families(adapter, colour)
    liner_families = _liner_paired_families(adapter)

    scored: list[Recommendation] = []
    for candidate in select(
        adapter, profile,
        predicate=lambda product: product.get("product_type") != "Lip Liner",
    ):
        best: tuple[float, dict[str, float], list[str], dict[str, Any] | None, dict[str, Any] | None] | None = None
        for variant, shade_profile in variant_shade_pairs(candidate):
            acc = FactorAccumulator(weights)
            score_shade(
                acc, candidate, profile, shade_profile,
                coordination=coordination,
                requested_ids=requested_ids,
                outfit_families=outfit_families,
                liner_families=liner_families,
            )
            score, breakdown = acc.finalize_makeup()
            acc.baseline()
            if best is None or score > best[0]:
                best = (score, breakdown, list(acc.reason_codes), variant, shade_profile)
        assert best is not None
        score, breakdown, codes, variant, shade_profile = best
        scored.append(make_recommendation(
            candidate,
            category="lips",
            score=score,
            reason_codes=codes,
            warnings=list(candidate.warnings),
            variant=variant,
            shade_profile=shade_profile,
            breakdown=breakdown if debug else None,
        ))
    return EngineResult(
        category="lips",
        items=rank(scored, limit=limit),
        notes={"liners_available": bool(adapter.liners())},
    )
