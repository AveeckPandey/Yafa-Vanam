"""Phase 2 recommendation engine: canonical models, dataset adapters, category engines.

Deterministic WHAT-decisions only. RAG provides FACTS, the LLM (later phase)
only explains; vector similarity never enters these scores. The legacy
app/v1.py stack keeps serving existing endpoints until golden parity proves
this package equivalent or better.
"""
from __future__ import annotations

from app.recommendation.canonical import CanonicalProfile, CoordinationHints
from app.recommendation.canonical.schemas import EngineResult, Recommendation

__all__ = [
    "CanonicalProfile",
    "CoordinationHints",
    "EngineResult",
    "Recommendation",
]
