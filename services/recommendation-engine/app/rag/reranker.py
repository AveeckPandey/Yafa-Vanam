"""Deterministic reranking of vector-search hits.

Phase 1 uses transparent heuristics only (no cross-encoder model): chunk-type
priors derived from query intent, lexical overlap, and a per-chunk-type
diversity cap so one section type cannot crowd out the rest of the answer.
"""

from __future__ import annotations

import re

from app.rag.repository import SearchHit

_TOKEN = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """a an and any are do does is it its me my of on the this that what which who
    you your i we they there here have has had will would can could should how why
    when where in into for from with about if at as be been by to""".split()
)

# Query intent -> chunk types that deserve a ranking boost.
_TYPE_PRIORS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("how do i use", "how to use", "apply", "application"), ("usage",)),
    (("warning", "safe", "safety", "irritat", "allerg"), ("warnings",)),
    (("smell", "scent", "fragrance", "notes", "aroma"), ("scent_profile",)),
    (("ingredient", "inci", "formula", "niacinamide", "panthenol"), ("ingredients_concept", "ingredients", "evidence")),
    (("routine", "step", "layer", "order", "before or after"), ("routine_position", "usage", "faq")),
    (("shade", "colour", "color", "undertone"), ("shade_information",)),
    (("designed for", "what is it", "tell me about", "overview", "positioned"), ("product_overview", "faq", "benefits")),
    (("evidence", "study", "research", "proven", "clinical", "verified"), ("evidence",)),
)
# Boost applied per matched prior group.
_PRIOR_BOOST = 0.12
# Lexical-overlap boost ceiling.
_OVERLAP_CEILING = 0.08
# At most this many chunks of the same type in a single response.
_MAX_PER_TYPE = 2


def content_tokens(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if token not in _STOPWORDS]


def rerank(hits: list[SearchHit], query: str, top_k: int) -> list[SearchHit]:
    """Return up to `top_k` hits, best first. Input order (similarity) breaks ties."""
    lowered = query.lower()
    boosted_types: set[str] = set()
    for phrases, types in _TYPE_PRIORS:
        if any(phrase in lowered for phrase in phrases):
            boosted_types.update(types)
    query_terms = set(content_tokens(query))

    scored: list[tuple[float, int, SearchHit]] = []
    for position, hit in enumerate(hits):
        score = hit.similarity
        if hit.chunk_type in boosted_types:
            score += _PRIOR_BOOST
        hit_terms = set(content_tokens(hit.content))
        if query_terms:
            overlap = len(query_terms & hit_terms) / len(query_terms)
            score += min(overlap * _OVERLAP_CEILING * 2, _OVERLAP_CEILING)
        # Stable tie-break: original similarity order wins.
        scored.append((score, -position, hit))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    selected: list[SearchHit] = []
    per_type: dict[str, int] = {}
    for _, _, hit in scored:
        if per_type.get(hit.chunk_type, 0) >= _MAX_PER_TYPE:
            continue
        per_type[hit.chunk_type] = per_type.get(hit.chunk_type, 0) + 1
        selected.append(hit)
        if len(selected) >= top_k:
            break
    return selected
