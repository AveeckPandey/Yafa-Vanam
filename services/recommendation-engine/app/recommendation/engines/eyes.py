"""Eyes engine: sub-engines per product type sharing one weight table.

- brows: brow_matching rows dominate (hair depth x temperature); outfit is
  NEVER a brow signal (dataset category_specific rule). Rows recommend named
  shades, so brows emit one row per matched shade in rule order.
- mascara/eyeliner: neutral tones are the default ranking signal; coloured
  options rank only through eye/outfit harmony.
- eyeshadow singles + palettes: per-shade/per-pan colour harmony; palettes
  stay ONE candidate scored by their best pan.

Eye colour, outfit and depth stay boosts inside the weighted normalization —
never gates.
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
    BROW_HAIR_DEPTH_TEMPERATURE_MATCH,
    BROW_SECONDARY_TONE_FIT,
    DESIRED_INTENSITY_MATCH,
    EYELINER_NEUTRAL_DEFAULT,
    MASCARA_DEFAULT_NEUTRAL,
    PALETTE_SINGLE_SELLABLE_SKU,
    REQUESTED_FINISH_OR_PRODUCT_MATCH,
    eye_colour_boost,
    look_style_priority,
    occasion_match,
    outfit_harmony,
    undertone_match,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import EYE_WEIGHTS, effective_weights

BROW_GRADE_STEP = 0.15      # 1st recommended tone 1.0, 2nd 0.85, ...
BROW_SECONDARY_GRADE = 0.4  # row matching only depth OR only temperature
SECONDARY_TONE_GRADE = 0.6  # eye-colour secondary tones vs boost tones

MASCARA_NEUTRAL_FAMILIES = {"black", "brown", "black_brown", "brown_black"}
EYELINER_NEUTRAL_FAMILIES = {"black", "brown", "charcoal", "black_brown", "brown_black"}


def _expanded_tokens(value: Any) -> set[str]:
    """Normalize a dataset token and split compound forms ("neutral-or-cool"
    matches profile "neutral" or "cool")."""
    normalized = normalize_token(value)
    return {normalized, *(part for part in normalized.split("_or_") if part)}


def _eye_rules(adapter: Any, profile: CanonicalProfile) -> dict[str, Any] | None:
    return adapter.eye_colour_rules(profile.eye_colour)


def _outfit_recommended_families(adapter: Any, colour: str | None) -> set[str]:
    if not colour:
        return set()
    for _group, table in (adapter.outfit_families() or {}).items():
        examples = {normalize_token(e) for e in table.get("examples") or []}
        if colour in examples:
            return {normalize_token(f) for f in table.get("recommended_eye_families") or []}
    return set()


def _style_priority_families(adapter: Any, profile: CanonicalProfile) -> set[str]:
    """Dataset look_styles keys drift between hyphens and underscores."""
    style_table = adapter.look_styles() or {}
    wanted = normalize_token(profile.style) if profile.style else None
    for key, value in style_table.items():
        if wanted and normalize_token(key) == wanted:
            return {normalize_token(f) for f in value.get("priority_families") or []}
    return set()


def _credit_colour_harmony(
    acc: FactorAccumulator,
    family: str | None,
    rules: dict[str, Any] | None,
    outfit_families: set[str],
    colour: str | None,
) -> None:
    """Eye-colour boosts, then outfit harmony — boosts only, never gates."""
    if rules and family:
        boost = {normalize_token(t) for t in rules.get("boost") or []}
        secondary = {normalize_token(t) for t in rules.get("secondary") or []}
        if any(family_matches(family, t) for t in boost):
            acc.credit(
                "eye_colour_compatibility", True,
                *(eye_colour_boost(t) for t in rules.get("boost") or []),
            )
        elif any(family_matches(family, t) for t in secondary):
            acc.credit(
                "eye_colour_compatibility", SECONDARY_TONE_GRADE,
                *(eye_colour_boost(t) for t in rules.get("secondary") or []),
            )
    if outfit_families and any(family_matches(family, f) for f in outfit_families):
        acc.credit("outfit_harmony", True, outfit_harmony(colour))


def _score_pan(
    acc: FactorAccumulator,
    profile: CanonicalProfile,
    shade_profile: dict[str, Any] | None,
    *,
    rules: dict[str, Any] | None,
    outfit_families: set[str],
    style_families: set[str],
    colour: str | None,
) -> None:
    """Shared eyeshadow/pan scoring over one shade profile's rec block."""
    rec = recommendation_block(shade_profile)
    family = color_family_of(shade_profile)

    if style_families and any(family_matches(family, f) for f in style_families):
        acc.credit("user_requested_product_or_look", True, look_style_priority(profile.style))

    _credit_colour_harmony(acc, family, rules, outfit_families, colour)

    intensity = normalize_token(profile.eye_intensity)
    pan_intensity = normalize_token((shade_profile.get("color_profile") or {}).get("intensity"))
    if intensity and pan_intensity and intensity == pan_intensity:
        acc.credit("desired_intensity", True, DESIRED_INTENSITY_MATCH)

    daypart = normalize_token(profile.daypart)
    daypart_hit = bool(daypart) and daypart in {normalize_token(d) for d in rec.get("daypart") or []}
    occasion_hit = canonical_occasion(profile.occasion) and occasion_tags_overlap(
        canonical_occasion(profile.occasion), rec.get("occasion_tags")
    )
    if daypart_hit or occasion_hit:
        codes = [occasion_match(canonical_occasion(profile.occasion))] if occasion_hit else []
        acc.credit("daypart_and_occasion", True, *codes)

    undertone = normalize_token(profile.undertone)
    if undertone and undertone in {normalize_token(u) for u in rec.get("undertone_compatibility") or []}:
        acc.credit("undertone_compatibility", True, undertone_match(profile.undertone))

    depth = normalize_token(profile.depth)
    if depth and depth in {normalize_token(d) for d in rec.get("complexion_depth_compatibility") or []}:
        acc.credit("complexion_depth_as_intensity_tuning", True)


def _matching_brow_row(adapter: Any, profile: CanonicalProfile) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """(primary_row, secondary_row) for the profile's hair colour/depth/temperature.

    Rows key on hair DEPTH tokens ("black", "medium-brown", ...); real profiles
    often state those as hair_colour, so both feed the depth side.
    """
    depth_tokens: set[str] = set()
    for value in (profile.hair_depth, profile.hair_colour):
        if value:
            depth_tokens |= _expanded_tokens(value)
    hair_temperature = normalize_token(profile.hair_temperature)
    if not depth_tokens and not hair_temperature:
        return None, None
    primary_row = None
    secondary_row = None
    for row in adapter.brow_rules():
        row_depths: set[str] = set()
        for depth in row.get("hair_depth") or []:
            row_depths |= _expanded_tokens(depth)
        row_temperatures = _expanded_tokens(row.get("hair_temperature"))
        depth_hit = bool(depth_tokens) and bool(depth_tokens & row_depths)
        temperature_hit = bool(hair_temperature) and hair_temperature in row_temperatures
        if depth_hit and temperature_hit:
            return row, None
        if (depth_hit or temperature_hit) and secondary_row is None:
            secondary_row = row
    return None, secondary_row


def _brow_shade_scores(
    adapter: Any,
    profile: CanonicalProfile,
    candidate: Candidate,
    weights: Any,
) -> list[tuple[float, dict[str, float], list[str], dict[str, Any] | None, dict[str, Any] | None]]:
    """One scored row per rule-recommended shade present on the product.

    Rule order is authority: position i grades 1 - i*BROW_GRADE_STEP. Outfit,
    eye colour and every other factor stay out of brow scoring.
    """
    primary_row, secondary_row = _matching_brow_row(adapter, profile)
    if primary_row is None and secondary_row is None:
        return []
    row = primary_row or secondary_row
    is_primary = primary_row is not None

    by_name: dict[str, tuple[dict[str, Any] | None, dict[str, Any] | None]] = {}
    for variant, shade_profile in variant_shade_pairs(candidate):
        name = (shade_profile or {}).get("name")
        if name and name not in by_name:
            by_name[name] = (variant, shade_profile)

    results = []
    for position, name in enumerate(row.get("recommended") or []):
        hit = by_name.get(name)
        if not hit:
            continue
        acc = FactorAccumulator(weights)
        grade = BROW_SECONDARY_GRADE if not is_primary else max(0.0, 1.0 - position * BROW_GRADE_STEP)
        code = BROW_HAIR_DEPTH_TEMPERATURE_MATCH if is_primary else BROW_SECONDARY_TONE_FIT
        acc.credit("eye_colour_compatibility", grade, code)
        score, breakdown = acc.finalize_makeup()
        results.append((score, breakdown, list(acc.reason_codes), hit[0], hit[1]))
    return results


def _score_product(
    candidate: Candidate,
    profile: CanonicalProfile,
    *,
    adapter: Any,
    rules: dict[str, Any] | None,
    outfit_families: set[str],
    style_families: set[str],
    colour: str | None,
    requested_ids: set[str],
    weights: Any,
) -> tuple[float, dict[str, float], list[str], dict[str, Any] | None, dict[str, Any] | None]:
    acc = FactorAccumulator(weights)
    product = candidate.product
    product_type = normalize_token(product.get("product_type"))

    requested_type = normalize_token(profile.raw.get("requested_eye_product_type"))
    if requested_type and requested_type == product_type:
        acc.credit("product_type_fit", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)
    if product["id"] in requested_ids:
        acc.credit("user_requested_product_or_look", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)

    is_palette = bool(product.get("palette_colors"))
    if is_palette:
        # Palette = ONE candidate; its best pan carries the codes/breakdown.
        best: tuple[float, FactorAccumulator] | None = None
        for pan in candidate.shade_profiles:
            pan_acc = FactorAccumulator(weights)
            _score_pan(
                pan_acc, profile, pan,
                rules=rules, outfit_families=outfit_families,
                style_families=style_families, colour=colour,
            )
            score, _ = pan_acc.finalize_makeup()
            if best is None or score > best[0]:
                best = (score, pan_acc)
        if best is not None:
            acc = best[1]
            acc.reason_codes.append(PALETTE_SINGLE_SELLABLE_SKU)
    else:
        for _variant, shade_profile in variant_shade_pairs(candidate):
            _score_pan(
                acc, profile, shade_profile,
                rules=rules, outfit_families=outfit_families,
                style_families=style_families, colour=colour,
            )
        families = {color_family_of(sp) for sp in candidate.shade_profiles}
        if product_type == "mascara":
            # Neutral defaults rank naturally; coloured mascara needs harmony.
            if families & MASCARA_NEUTRAL_FAMILIES:
                acc.credit("eye_colour_compatibility", True, MASCARA_DEFAULT_NEUTRAL)
            intensity = normalize_token(profile.eye_intensity)
            if intensity in {"bold", "strong", "high", "dramatic"} and "black" in families:
                acc.credit("desired_intensity", True, DESIRED_INTENSITY_MATCH)
        elif product_type == "eyeliner":
            if families & EYELINER_NEUTRAL_FAMILIES:
                acc.credit("eye_colour_compatibility", True, EYELINER_NEUTRAL_DEFAULT)

    score, breakdown = acc.finalize_makeup()
    acc.baseline()
    variant = candidate.primary_variant()
    shade_profile = candidate.shade_profiles[0] if candidate.shade_profiles else None
    return score, breakdown, list(acc.reason_codes), variant, shade_profile


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("eyes")
    weights = effective_weights("eyes", adapter.weights_table(), EYE_WEIGHTS)
    requested_ids = raw_requested_ids(profile)
    rules = _eye_rules(adapter, profile)
    colour = outfit_colour(profile)
    outfit_families = _outfit_recommended_families(adapter, colour)
    style_families = _style_priority_families(adapter, profile)

    scored: list[Recommendation] = []
    for candidate in select(adapter, profile):
        if normalize_token(candidate.product.get("product_type")) == "brows":
            brow_rows = _brow_shade_scores(adapter, profile, candidate, weights)
            if brow_rows:
                for score, breakdown, codes, variant, shade_profile in brow_rows:
                    scored.append(make_recommendation(
                        candidate,
                        category="eyes",
                        score=score,
                        reason_codes=codes,
                        warnings=list(candidate.warnings),
                        variant=variant,
                        shade_profile=shade_profile,
                        breakdown=breakdown if debug else None,
                    ))
                continue  # shade-level rows replace the product-level default
        score, breakdown, codes, variant, shade_profile = _score_product(
            candidate, profile,
            adapter=adapter,
            rules=rules,
            outfit_families=outfit_families,
            style_families=style_families,
            colour=colour,
            requested_ids=requested_ids,
            weights=weights,
        )
        scored.append(make_recommendation(
            candidate,
            category="eyes",
            score=score,
            reason_codes=codes,
            warnings=list(candidate.warnings),
            variant=variant,
            shade_profile=shade_profile,
            breakdown=breakdown if debug else None,
        ))
    return EngineResult(category="eyes", items=rank(scored, limit=limit))
