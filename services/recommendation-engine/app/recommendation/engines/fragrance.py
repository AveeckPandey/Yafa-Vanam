"""Fragrance engine: scent-profile overlap over the dataset's own vocabulary.

Wanted tokens come only from what the profile states (families/facets/mood,
seasons/occasions/intensity); an empty fragrance profile degrades every item
to catalogue baseline rather than inventing preferences.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.recommendation.adapters import get_adapter
from app.recommendation.candidate_filter import select
from app.recommendation.canonical.normalization import normalize_token
from app.recommendation.canonical.schemas import (
    CanonicalProfile,
    CoordinationHints,
    EngineResult,
)
from app.recommendation.engines.base import make_recommendation
from app.recommendation.reason_codes import (
    FRAGRANCE_PROFILE_OVERLAP,
    FRAGRANCE_SEASON_OCCASION_MATCH,
    SAME_SCENT_LINE_LAYERING,
)
from app.recommendation.scorer import FactorAccumulator
from app.recommendation.weights import FRAGRANCE_WEIGHTS, effective_weights

MAX_LAYERING_GROUPS = 2
MAX_LAYERING_PER_GROUP = 2


def _wanted_tokens(profile: CanonicalProfile) -> tuple[set[str], set[str]]:
    """(core tokens for overlap grading, season/occasion tokens) from prefs."""
    prefs = profile.fragrance or {}
    core: set[str] = set()
    for key in ("families", "facets", "mood"):
        values = prefs.get(key) or []
        core.update(normalize_token(v) for v in values if v)
    context: set[str] = set()
    for key in ("season", "seasons", "occasion", "occasions"):
        values = prefs.get(key) or []
        if isinstance(values, str):
            values = [values]
        context.update(normalize_token(v) for v in values if v)
    return core, context


def _fragrance_corpus(fragrance: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("family", "facets", "mood", "season", "occasion"):
        values = fragrance.get(key)
        if isinstance(values, str):
            values = [values]
        tokens.update(normalize_token(v) for v in (values or []) if v)
    return tokens


def score_candidate(candidate: Any, profile: CanonicalProfile) -> tuple[float, dict[str, float], list[str], list[str]]:
    acc = FactorAccumulator(effective_weights("fragrance", None, FRAGRANCE_WEIGHTS))
    fragrance = candidate.product.get("fragrance_profile") or {}
    core, context = _wanted_tokens(profile)

    if core:
        corpus = _fragrance_corpus(fragrance)
        matched = core & corpus
        if matched:
            grade = min(1.0, len(matched) / max(1, len(core)))
            acc.credit("scent_profile_overlap", grade, FRAGRANCE_PROFILE_OVERLAP)

    if context:
        matched_context = context & _fragrance_corpus(fragrance)
        if matched_context:
            acc.credit("season_and_occasion", min(1.0, len(matched_context) / max(1, len(context))), FRAGRANCE_SEASON_OCCASION_MATCH)

    intensity = normalize_token((profile.fragrance or {}).get("intensity"))
    product_intensity = normalize_token(fragrance.get("intensity_positioning"))
    if intensity and product_intensity:
        acc.credit("intensity_positioning", intensity == product_intensity)

    score, breakdown = acc.finalize_makeup()
    acc.baseline()
    return score, breakdown, list(acc.reason_codes), list(candidate.warnings)


def recommend(
    profile: CanonicalProfile,
    *,
    limit: int = 3,
    coordination: CoordinationHints | None = None,
    debug: bool = False,
) -> EngineResult:
    adapter = get_adapter("no_shades")
    scored: list[tuple[str | None, Any]] = []
    for candidate in select(adapter, profile):
        score, breakdown, codes, warnings = score_candidate(candidate, profile)
        item = make_recommendation(
            candidate,
            category="fragrance",
            score=score,
            reason_codes=codes,
            warnings=warnings,
            variant=candidate.primary_variant(),
            breakdown=breakdown if debug else None,
        )
        line = ((candidate.product.get("fragrance_profile") or {}).get("related_scent_line")) or None
        scored.append((line, item))
    scored.sort(key=lambda row: (-row[1].score, row[1].product_id))
    items = [item for _, item in scored[:limit]]
    notes: dict[str, Any] = {"layering": layering_notes(scored)}
    return EngineResult(category="fragrance", items=items, notes=notes)


def layering_notes(scored: list[tuple[str | None, Any]]) -> list[dict[str, Any]]:
    """Same-scent-line pairings are catalogue-family coordination suggestions,
    never longevity claims — capped so notes stay small."""
    lines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line, item in scored:
        if line:
            lines[line].append({"product_id": item.product_id, "name": item.product_name})
    notes = []
    for line, products in sorted(lines.items()):
        if len(products) > 1:
            notes.append({
                "scent_line": line,
                "products": products[:MAX_LAYERING_PER_GROUP],
                "reason_code": SAME_SCENT_LINE_LAYERING,
                "reason": "Same scent line; pairing is a catalogue-family coordination suggestion, not a longevity claim.",
            })
        if len(notes) >= MAX_LAYERING_GROUPS:
            break
    return notes
