"""Complexion engine: TWO stages that never share a number (spec §17).

resolve_shades() answers "which shade" with ΔE00 / depth distance only.
rank_formulas() answers "which product/formula" with skin-type / finish /
coverage / occasion only. The deleted v1 blend `1/(1+dE/8)*.7 + formula*.3`
stays deleted; the primary ShadeMatch travels in EngineResult.notes instead.

Undertone is a tie-breaker, never a prefilter: every master shade stays
rankable regardless of axis.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters import get_adapter
from app.recommendation.candidate_filter import select
from app.recommendation.canonical.enums import axis_for, depth_index_for
from app.recommendation.canonical.normalization import canonical_occasion, normalize_token
from app.recommendation.canonical.schemas import (
    Candidate,
    CanonicalProfile,
    CoordinationHints,
    EngineResult,
    Recommendation,
    ShadeMatch,
    SourceRef,
)
from app.recommendation.colorimetry import ciede2000, classify_delta_e, piecewise_confidence
from app.recommendation.engines.base import make_recommendation
from app.recommendation.reason_codes import (
    REQUESTED_FINISH_OR_PRODUCT_MATCH,
    SHADE_CONFIRMED_CODE,
    SHADE_DEPTH_UNDERTONE_TIEBREAK,
    SHADE_LAB_MEASURED_DISTANCE,
    SHADE_NEIGHBOUR_GRAPH_FALLBACK,
    SKIN_TYPE_BEST_FOR,
    SKIN_TYPE_CAUTION_PENALTY,
    SKIN_TYPE_COMPATIBLE,
    occasion_match,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import COMPLEXION_FORMULA_WEIGHTS, effective_weights

TOP_SHADES = 3  # distinct winning shade codes carried into matches

FOUNDATION_TYPES = {"Foundation", "Skin Tint", "Powder Foundation"}
SUPPORT_ROLES = {
    "concealer": "Concealer",
    "powder": "Setting Powder",
    "corrector": "Color Corrector",
    "bronzer": "Bronzer",
    "contour": "Contour",
    "highlighter": "Highlighter",
}


def _complete_lab(lab: dict[str, float] | None) -> tuple[float, float, float] | None:
    if lab and all(isinstance(lab.get(k), (int, float)) for k in ("L", "a", "b")):
        return (float(lab["L"]), float(lab["a"]), float(lab["b"]))
    return None


def _winning_shade_codes(
    adapter: Any,
    profile: CanonicalProfile,
) -> tuple[list[str], dict[str, tuple[float, str | None]], bool]:
    """Rank master shades by exactly one active mode; return top distinct codes.

    Returns (codes, {code: (distance, resolution_code)}, neighbour_fallback_used).
    """
    known = (profile.shade_code or "").upper() or None
    lab = _complete_lab(profile.lab)
    target_depth = depth_index_for(profile.depth)
    wanted_axis = axis_for(profile.undertone)

    ranked: list[tuple[float, str, str | None]] = []  # (distance, code, resolution_code)
    if known:
        matched = [
            (0.0, str(shade.get("code")).upper(), SHADE_CONFIRMED_CODE)
            for shade in adapter.shade_records()
            if str(shade.get("code") or "").upper() == known
        ]
        if matched:
            return [matched[0][1]], {matched[0][1]: (0.0, SHADE_CONFIRMED_CODE)}, False

    neighbour_fallback = False
    if lab is not None:
        for shade in adapter.shade_records():
            measured = ((shade.get("measured_colour") or {}).get("cielab")) or {}
            if not all(isinstance(measured.get(k), (int, float)) for k in ("L", "a", "b")):
                continue
            distance = ciede2000(lab, (measured["L"], measured["a"], measured["b"]))
            ranked.append((distance, str(shade.get("code")).upper(), SHADE_LAB_MEASURED_DISTANCE))
    else:
        # Depth pseudo-distance with undertone tie-break (v1 port); every shade
        # stays ranked — the axis never prefilters. Missing depth falls back to
        # v1's catalogue-default ordering at index 4.
        target_depth = target_depth or 4
        depth_axis_present = any(
            axis_for(shade.get("undertone")) == wanted_axis
            for shade in adapter.shade_records()
            if shade.get("depth_index") == target_depth
        )
        neighbour_fallback = bool(wanted_axis) and not depth_axis_present
        for shade in adapter.shade_records():
            distance = abs(int(shade.get("depth_index") or 4) - target_depth) * 8.0
            resolution = None
            if wanted_axis and axis_for(shade.get("undertone")) == wanted_axis:
                distance -= 2.0
                resolution = SHADE_DEPTH_UNDERTONE_TIEBREAK
            ranked.append((distance, str(shade.get("code")).upper(), resolution))

    distances: dict[str, tuple[float, str | None]] = {}
    ordered: list[str] = []
    for distance, code, resolution in sorted(ranked, key=lambda row: (row[0], row[1])):
        if code not in distances:
            distances[code] = (distance, resolution)
            ordered.append(code)
    return ordered[:TOP_SHADES], {c: distances[c] for c in ordered[:TOP_SHADES]}, neighbour_fallback


def resolve_shades(
    adapter: Any,
    profile: CanonicalProfile,
    *,
    limit_matches: int = 6,
) -> list[ShadeMatch]:
    """Stage one: shade resolution across foundations — colour math ONLY."""
    thresholds = adapter.delta_e_thresholds()
    anchors = adapter.confidence_anchors()
    codes, distances, neighbour_fallback = _winning_shade_codes(adapter, profile)
    code_set = set(codes)

    records = {str(shade.get("code")).upper(): shade for shade in adapter.shade_records()}
    matches: list[ShadeMatch] = []
    for product in adapter.foundations():
        for variant in product.get("variants", []):
            shade_block = variant.get("shade") or {}
            code = str(shade_block.get("code") or "").upper()
            if code not in code_set:
                continue
            record = records.get(code) or shade_block
            distance, resolution_code = distances[code]
            codes_out: list[str] = []
            if resolution_code:
                codes_out.append(resolution_code)
            if neighbour_fallback and profile.undertone:
                codes_out.append(SHADE_NEIGHBOUR_GRAPH_FALLBACK)
            measured = ((record.get("measured_colour") or {}).get("cielab")) or {}
            delta_e: float | None = None
            if _complete_lab(profile.lab) and all(isinstance(measured.get(k), (int, float)) for k in ("L", "a", "b")):
                delta_e = ciede2000(_complete_lab(profile.lab), (measured["L"], measured["a"], measured["b"]))  # type: ignore[arg-type]
            band = classify_delta_e(distance if delta_e is None else delta_e, thresholds)
            confidence = piecewise_confidence(distance if delta_e is None else delta_e, anchors, profile.capture_confidence)
            matches.append(
                ShadeMatch(
                    code=code,
                    name=record.get("name"),
                    hex=record.get("hex"),
                    depth_index=int(record.get("depth_index") or 0),
                    undertone_axis=axis_for(record.get("undertone")),
                    delta_e00=round(delta_e, 3) if delta_e is not None else None,
                    match_class=band,
                    confidence=round(confidence, 3),
                    reason_codes=codes_out,
                    product_id=product["id"],
                    variant_id=variant.get("id"),
                    source=SourceRef(file=adapter.filename),
                )
            )
            if len(matches) >= limit_matches * len(code_set):
                break
        if len(matches) >= limit_matches * len(code_set):
            break
    matches.sort(key=lambda m: (m.code != codes[0], m.product_id, m.variant_id or ""))
    return matches


def _formula_factors(acc: FactorAccumulator, product: dict[str, Any], profile: CanonicalProfile) -> None:
    """Strictly non-colour inputs. Colour never enters this accumulator."""
    rp = product.get("recommendation_profile") or {}
    blocks = rp.get("skin_types") or {}

    if profile.skin_types:
        wanted = {normalize_token(v) for v in profile.skin_types}
        best_for = {normalize_token(v) for v in blocks.get("best_for") or []}
        compatible = {normalize_token(v) for v in blocks.get("compatible_with") or []}
        caution = {normalize_token(v) for v in blocks.get("use_with_caution") or []}
        if wanted & best_for or "all_skin_types" in best_for:
            acc.credit("skin_type_fit", True, SKIN_TYPE_BEST_FOR)
        elif wanted & compatible or "all_skin_types" in compatible:
            acc.credit("skin_type_fit", 0.7, SKIN_TYPE_COMPATIBLE)
        elif wanted & caution:
            acc.credit("skin_type_fit", 0.2, SKIN_TYPE_CAUTION_PENALTY)

    text = f"{product.get('name', '')} {product.get('product_type', '')} {product.get('subcategory', '')}".lower()
    if profile.finish and normalize_token(profile.finish).replace("_", " ") in text:
        acc.credit("finish_preference", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)
    if profile.coverage and normalize_token(profile.coverage).replace("_", " ") in text:
        acc.credit("coverage_preference", True, REQUESTED_FINISH_OR_PRODUCT_MATCH)

    occasion = canonical_occasion(profile.occasion)
    if occasion:
        product_occasions = {canonical_occasion(tag) for tag in rp.get("occasion") or []}
        if occasion in product_occasions:
            acc.credit("occasion_wear_goal", True, occasion_match(occasion))


def score_formula_candidate(candidate: Candidate, profile: CanonicalProfile) -> tuple[float, dict[str, float], list[str]]:
    weights = effective_weights("complexion_formula", None, COMPLEXION_FORMULA_WEIGHTS)
    acc = FactorAccumulator(weights)
    _formula_factors(acc, candidate.product, profile)
    score, breakdown = acc.finalize_makeup()
    acc.baseline()
    return score, breakdown, list(acc.reason_codes)


def rank_formulas(
    profile: CanonicalProfile,
    candidates: list[Candidate],
    *,
    limit: int,
    debug: bool = False,
) -> list[Recommendation]:
    """Stage two: formula ranking — zero colour terms by construction."""
    scored: list[tuple[float, Recommendation]] = []
    for candidate in candidates:
        score, breakdown, codes = score_formula_candidate(candidate, profile)
        scored.append((
            score,
            make_recommendation(
                candidate,
                category="complexion",
                score=score,
                reason_codes=codes,
                warnings=list(candidate.warnings),
                variant=candidate.primary_variant(),
                breakdown=breakdown if debug else None,
            ),
        ))
    scored.sort(key=lambda row: (-row[0], row[1].product_id))
    return [item for _, item in scored[:limit]]


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("skin")
    shade_matches = resolve_shades(adapter, profile)
    primary_code = shade_matches[0].code if shade_matches else None

    def foundation_only(product: dict[str, Any]) -> bool:
        return product.get("product_type") in FOUNDATION_TYPES

    candidates = select(adapter, profile, predicate=foundation_only)
    items = rank_formulas(profile, candidates, limit=limit, debug=debug)

    # Attach each foundation's variant carrying the primary resolved shade.
    if primary_code:
        variants_by_product: dict[str, str] = {}
        for match in shade_matches:
            variants_by_product.setdefault(match.product_id, match.variant_id)
        for item in items:
            item.variant_id = item.variant_id or variants_by_product.get(item.product_id)

    support: dict[str, dict[str, Any]] = {}
    for role, product_type in SUPPORT_ROLES.items():
        role_candidates = select(
            adapter, profile,
            predicate=lambda product, expected=product_type: product.get("product_type") == expected,
        )
        ranked = rank_formulas(profile, role_candidates, limit=1, debug=False)
        if ranked:
            support[role] = ranked[0].model_dump(mode="json")

    notes: dict[str, Any] = {
        "primary_shade": shade_matches[0].model_dump() if shade_matches else None,
        "shade_matches": [match.model_dump() for match in shade_matches] if debug else None,
        "support": support or None,
    }
    return EngineResult(
        category="complexion",
        items=items,
        notes={key: value for key, value in notes.items() if value is not None},
    )
