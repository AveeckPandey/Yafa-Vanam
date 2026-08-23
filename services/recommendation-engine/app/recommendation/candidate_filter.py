"""Candidate gating: status, hard exclusions, requested products, palette integrity.

Hard exclusions REJECT regardless of any positive signal (spec Test E); soft
penalties never exclude — they surface as warnings for the scorer. Palettes
stay ONE candidate with pans attached (fan-out corrupts diversity ranking).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.recommendation.adapters.base import BaseAdapter
from app.recommendation.canonical.normalization import normalize_token
from app.recommendation.canonical.schemas import Candidate, CanonicalProfile
from app.recommendation.reason_codes import soft_penalty

logger = logging.getLogger(__name__)

PREGNANCY_ALIAS = "pregnant_or_planning_pregnancy"
PREGNANCY_PREFIXES = ("pregnant", "planning_pregnancy", "pregnancy")


def _matches_safety_condition(condition: str, profile: CanonicalProfile) -> bool:
    """Strict v1 semantics: exact token match plus the pregnancy aliasing."""
    if condition in profile.safety_conditions:
        return True
    return condition == PREGNANCY_ALIAS and any(
        token.startswith(PREGNANCY_PREFIXES) for token in profile.safety_conditions
    )


@dataclass
class FilterOutcome:
    excluded: bool = False
    reason_code: str | None = None
    warnings: list[str] = field(default_factory=list)


def evaluate(product: dict[str, Any], profile: CanonicalProfile) -> FilterOutcome:
    """Status gate + hard exclusions + soft-penalty warnings for one product."""
    outcome = FilterOutcome()
    if product.get("status") not in {"active", None}:
        outcome.excluded = True
        outcome.reason_code = f"status_{normalize_token(product.get('status'))}"
        return outcome

    rp = product.get("recommendation_profile") or {}
    for rule in rp.get("hard_exclusions") or []:
        condition = normalize_token(rule.get("condition") if isinstance(rule, dict) else str(rule))
        if condition and _matches_safety_condition(condition, profile):
            outcome.excluded = True
            outcome.reason_code = f"hard_exclusion_{condition}"
            return outcome  # rejection is unconditional — positives can't compensate

    for rule in rp.get("soft_penalties") or []:
        condition = normalize_token(rule.get("condition", "")) if isinstance(rule, dict) else ""
        sensitivity_hit = condition == "sensitive_or_reactive_skin" and profile.sensitivity in {
            "medium", "high", "sensitive",
        }
        if condition and (_matches_safety_condition(condition, profile) or sensitivity_hit):
            outcome.warnings.append(soft_penalty(condition))
    return outcome


def select(
    adapter: BaseAdapter,
    profile: CanonicalProfile,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    requested_product_ids: set[str] | None = None,
) -> list[Candidate]:
    """Filter an adapter's catalogue into scorable Candidates.

    - one candidate per product; palettes keep their pans in shade_profiles
    - hard-excluded / inactive products are dropped (Test E)
    - when requested_product_ids is given, only those products pass
    """
    selected: list[Candidate] = []
    for product in adapter.active():
        if predicate and not predicate(product):
            continue
        if requested_product_ids is not None and product["id"] not in requested_product_ids:
            continue
        outcome = evaluate(product, profile)
        if outcome.excluded:
            continue
        variants = [v for v in product.get("variants", []) if v.get("is_active", True)]
        candidate = Candidate(
            product=product,
            variants=variants,
            source_file=adapter.filename,
            shade_profiles=_attach_shade_profiles(adapter, product),
            warnings=list(outcome.warnings),
        )
        selected.append(candidate)
    return selected


def _attach_shade_profiles(adapter: BaseAdapter, product: dict[str, Any]) -> list[dict[str, Any]]:
    """Category-specific per-shade profiles joined by the owning adapter.

    Palettes contribute their pans here so engines see pan colour data without
    ever treating a pan as a sellable variant.
    """
    join = getattr(adapter, "shade_profiles_for_product", None)
    if callable(join):
        try:
            return join(product["id"])
        except Exception:  # noqa: BLE001 - missing joins degrade to product-level scoring
            logger.debug("no shade-profile join for %s", product.get("id"), exc_info=True)
            return []
    return []
