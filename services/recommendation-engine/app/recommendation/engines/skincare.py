"""Skincare engine: the datasets' own signed constant scale, never a parallel one.

Signals fire in the dataset's ranking_order (hard exclusions are already gone
by the time candidates reach us). The raw signal sum stays in every breakdown
so the clamp01 mapping through NORMALIZATION_MIN/MAX is fully auditable.
"""
from __future__ import annotations

from typing import Any

from app.recommendation.adapters import get_adapter
from app.recommendation.candidate_filter import _matches_safety_condition, select
from app.recommendation.canonical.normalization import normalize_token
from app.recommendation.canonical.schemas import (
    Candidate,
    CanonicalProfile,
    CoordinationHints,
    EngineResult,
    Recommendation,
)
from app.recommendation.engines.base import make_recommendation
from app.recommendation.reason_codes import (
    COMPATIBILITY_REQUIRES_FORMULA_CONFIRMATION,
    CONCERN_PRIMARY_MATCH,
    CONCERN_SECONDARY_SUPPORT,
    EXPERIENCE_LEVEL_FIT,
    GOAL_DIRECT_MATCH,
    SKIN_TYPE_BEST_FOR,
    SKIN_TYPE_CAUTION_PENALTY,
    SKIN_TYPE_COMPATIBLE,
    compatibility_pairing,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import SKINCARE_SCALE

# routine.step values that predate the template role names map forward;
# anything unmapped lands after the templated slots.
ROUTINE_ROLE_ALIASES = {
    "body_moisturizer": "moisturizer",
    "mask": "serum_or_treatment",
    "exfoliation": "serum_or_treatment",
    "sunscreen": "sunscreen_if_validated",
}

MAX_GOAL_CREDITS = 2


def _skincare_predicate(product: dict[str, Any]) -> bool:
    return not product.get("fragrance_profile") and product.get("product_type") not in {
        "Face Primer",
        "Setting Spray",
    }


def _skin_type_signal(acc: FactorAccumulator, rp: dict[str, Any], profile: CanonicalProfile) -> None:
    wanted = {normalize_token(v) for v in profile.skin_types}
    if not wanted:
        return
    blocks = rp.get("skin_types") or {}
    best_for = {normalize_token(v) for v in blocks.get("best_for") or []}
    compatible = {normalize_token(v) for v in blocks.get("compatible_with") or []}
    caution = {normalize_token(v) for v in blocks.get("use_with_caution") or []}
    if wanted & best_for or "all_skin_types" in best_for:
        acc.add_signal(SKINCARE_SCALE.BEST_FOR_MATCH, SKIN_TYPE_BEST_FOR)
    elif wanted & compatible or "all_skin_types" in compatible:
        acc.add_signal(SKINCARE_SCALE.COMPATIBLE_MATCH, SKIN_TYPE_COMPATIBLE)
    elif wanted & caution:
        acc.add_signal(SKINCARE_SCALE.TOLERANCE_CONCERN, SKIN_TYPE_CAUTION_PENALTY)


def _concern_signals(acc: FactorAccumulator, rp: dict[str, Any], profile: CanonicalProfile) -> None:
    wanted = {normalize_token(c) for c in profile.concerns}
    if not wanted:
        return
    blocks = rp.get("concerns") or {}
    primary = {normalize_token(c) for c in blocks.get("primary") or []}
    secondary = {normalize_token(c) for c in blocks.get("secondary") or []}
    if wanted & primary:
        acc.add_signal(SKINCARE_SCALE.BEST_FOR_MATCH, CONCERN_PRIMARY_MATCH)
    elif wanted & secondary:
        acc.add_signal(SKINCARE_SCALE.SUPPORTING_FEATURE, CONCERN_SECONDARY_SUPPORT)


def _goal_signals(acc: FactorAccumulator, rp: dict[str, Any], profile: CanonicalProfile) -> None:
    wanted = profile.raw.get("goals") or profile.raw.get("skincare_goals")
    if not wanted:
        return
    wanted_set = {normalize_token(g) for g in (wanted if isinstance(wanted, list) else [wanted])}
    product_goals = {normalize_token(g) for g in rp.get("goals") or []}
    for _ in range(min(MAX_GOAL_CREDITS, len(wanted_set & product_goals))):
        acc.add_signal(SKINCARE_SCALE.SUPPORTING_FEATURE, GOAL_DIRECT_MATCH)


def _experience_signal(acc: FactorAccumulator, rp: dict[str, Any], profile: CanonicalProfile) -> None:
    level = profile.raw.get("experience_level")
    if not level:
        return  # never invent an experience level the profile didn't state
    levels = {normalize_token(v) for v in rp.get("experience_level") or []}
    if normalize_token(level) in levels:
        acc.add_signal(SKINCARE_SCALE.SUPPORTING_FEATURE, EXPERIENCE_LEVEL_FIT)


def _compatibility_signals(acc: FactorAccumulator, product: dict[str, Any], profile: CanonicalProfile) -> None:
    """Concept-keyed pairing rules vs user-supplied ingredient concepts.

    Every rule carries requires_formula_confirmation=True, so a firing always
    surfaces as a warning — never as a claim.
    """
    concepts = profile.raw.get("ingredient_concepts")
    if not concepts:
        return
    wanted = {normalize_token(c) for c in (concepts if isinstance(concepts, list) else [concepts])}
    for rule in ((product.get("compatibility") or {}).get("rules")) or []:
        concept = normalize_token(rule.get("with", ""))
        delta = rule.get("score_delta")
        if concept and concept in wanted and isinstance(delta, (int, float)):
            acc.add_signal(
                float(delta),
                compatibility_pairing(concept),
                warning=COMPATIBILITY_REQUIRES_FORMULA_CONFIRMATION,
            )


def _soft_penalty_signals(acc: FactorAccumulator, candidate: Candidate, profile: CanonicalProfile) -> None:
    """Same condition semantics as candidate_filter.evaluate(); the warning
    itself rides on the Recommendation via candidate.warnings."""
    rp = candidate.product.get("recommendation_profile") or {}
    for rule in rp.get("soft_penalties") or []:
        condition = normalize_token(rule.get("condition", "")) if isinstance(rule, dict) else ""
        hit = bool(condition) and (
            _matches_safety_condition(condition, profile)
            or (condition == "sensitive_or_reactive_skin" and profile.sensitivity in {"medium", "high", "sensitive"})
        )
        if hit:
            acc.penalize(SKINCARE_SCALE.MINOR_MISMATCH)


def score_candidate(candidate: Candidate, profile: CanonicalProfile) -> tuple[float, dict[str, float], list[str], list[str]]:
    """(score, breakdown, reason_codes, warnings) — warnings merge the filter
    pass with any accumulator-level confirmations (compatibility rules)."""
    acc = FactorAccumulator()
    product = candidate.product
    rp = product.get("recommendation_profile") or {}
    _skin_type_signal(acc, rp, profile)
    _concern_signals(acc, rp, profile)
    _goal_signals(acc, rp, profile)
    _experience_signal(acc, rp, profile)
    _compatibility_signals(acc, product, profile)
    _soft_penalty_signals(acc, candidate, profile)
    codes = list(acc.reason_codes)
    codes.extend(code for code in candidate.warnings if code not in codes)
    warnings = list(acc.warnings)
    warnings.extend(code for code in candidate.warnings if code not in warnings)
    score, breakdown = acc.finalize_skincare()
    if not codes:
        codes.append("catalogue_baseline")
    return score, breakdown, codes, warnings


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("no_shades")
    ranked: list[tuple[float, Recommendation, Candidate]] = []
    for candidate in select(adapter, profile, predicate=_skincare_predicate):
        score, breakdown, codes, warnings = score_candidate(candidate, profile)
        item = make_recommendation(
            candidate,
            category="skincare",
            score=score,
            reason_codes=codes,
            warnings=warnings,
            variant=candidate.primary_variant(),
            breakdown=breakdown if debug else None,
        )
        ranked.append((score, item, candidate))
    ranked.sort(key=lambda row: (-row[0], row[1].product_id))
    items = [item for _, item, _ in ranked[:limit]]
    notes: dict[str, Any] = {
        "routine": build_routine(ranked, adapter.routine_builder()),
    }
    return EngineResult(category="skincare", items=items, notes=notes)


def build_routine(
    ranked: list[tuple[float, Recommendation, Candidate]],
    builder: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Fill am/pm template slots greedily by rank, one product per role.

    Products whose routine.step maps to no template slot land under
    "additional" so nothing silently disappears.
    """
    routines: dict[str, list[dict[str, Any]]] = {}
    for time_key, template in (("am", builder.get("am_template") or []), ("pm", builder.get("pm_template") or [])):
        slots: dict[str, dict[str, Any]] = {
            str(entry.get("role")): {"step": entry.get("step"), "role": entry.get("role"),
                                     "product_id": None, "name": None}
            for entry in template if entry.get("role")
        }
        additional: list[dict[str, Any]] = []
        filled: set[str] = set()
        placed_in_time: set[str] = set()
        for _, item, candidate in ranked:
            step = normalize_token(((candidate.product.get("recommendation_profile") or {}).get("routine") or {}).get("step"))
            role = ROUTINE_ROLE_ALIASES.get(step or "", step)
            if role and role in slots and role not in filled:
                slots[role]["product_id"] = item.product_id
                slots[role]["name"] = item.product_name
                filled.add(role)
                placed_in_time.add(item.product_id)
            elif role not in slots and item.product_id not in placed_in_time:
                additional.append({"step": None, "role": step, "product_id": item.product_id, "name": item.product_name})
        routines[time_key] = [slot for slot in slots.values() if slot["product_id"]] + additional[:3]
    return routines
