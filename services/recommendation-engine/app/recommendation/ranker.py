"""Deterministic ranking: score sort, stable ties, colour-family diversity.

Ports v1's diversity rule (once two items are selected, later duplicates of an
already-represented family are skipped) but parameterized and pure — M3's
cohesion damping arrives as another accumulator term, not surgery here.
"""
from __future__ import annotations

from typing import Callable, Sequence

from app.recommendation.canonical.schemas import Recommendation

DEFAULT_DIVERSITY_KEY: Callable[[Recommendation], str] = lambda item: item.color_family or "none"


def rank(
    scored: Sequence[Recommendation],
    *,
    limit: int,
    diversity_key: Callable[[Recommendation], str] = DEFAULT_DIVERSITY_KEY,
    diversity_freeze_after: int = 2,
) -> list[Recommendation]:
    """Sort by (-score, product_id, variant_id), shape the page with family
    diversity, then backfill by score order if diversity starved the page.

    The freeze rule is v1's ("don't return a stream of the same family"), but
    small category pools (cheeks has six products) can exhaust every family
    before the page fills — an under-filled page helps nobody, so deferred
    items return in score order after the diverse head.
    """
    ordered = sorted(
        scored,
        key=lambda item: (-item.score, item.product_id, item.variant_id or ""),
    )
    selected: list[Recommendation] = []
    deferred: list[Recommendation] = []
    seen_families: set[str] = set()
    for item in ordered:
        family = diversity_key(item)
        if len(selected) >= diversity_freeze_after and family in seen_families:
            deferred.append(item)
            continue
        selected.append(item)
        seen_families.add(family)
        if len(selected) >= limit:
            break
    for item in deferred:
        if len(selected) >= limit:
            break
        selected.append(item)
    return selected
