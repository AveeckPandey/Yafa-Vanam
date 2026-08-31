"""Production RAG safety decisions shared by retrieval and generation.

The rules here are deliberately deterministic and auditable.  They do not try
to "fix" a bad source with another model: unsafe, conflicting, stale, or
over-budget evidence is withheld and the caller must say it cannot confirm.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from app.rag.models import TrustLevel
from app.rag.repository import SearchHit

_INSTRUCTION = re.compile(
    r"\b(ignore (all |previous |prior )?(instructions|rules)|system prompt|developer message|"
    r"reveal (a )?(secret|password|token)|act as|jailbreak|tool call|follow (these|my) instructions|"
    r"override (the )?(policy|rules)|do not obey|begin system|assistant role)\b|"
    r"<\s*(script|system|assistant)|\[\s*inst\s*\]",
    re.IGNORECASE,
)
_TRUST_RANK = {
    TrustLevel.VERIFIED.value: 5,
    TrustLevel.AUTHORITATIVE_CATALOGUE.value: 4,
    TrustLevel.BRAND_CONFIRMED.value: 3,
    TrustLevel.RESEARCHED_QUALIFIED.value: 2,
}


def contains_prompt_injection(text: str, metadata: dict[str, Any] | None = None) -> bool:
    """Treat instructions inside knowledge as hostile data, never agent input."""
    if metadata and metadata.get("source_security_status") in {"quarantined", "rejected"}:
        return True
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(character for character in normalized if character not in "\u200b\u200c\u200d\ufeff")
    return bool(_INSTRUCTION.search(normalized))


@dataclass(frozen=True)
class EvidenceSelection:
    hits: list[SearchHit]
    conflicts: list[str]
    rejected_injection: int


def select_safe_evidence(hits: Iterable[SearchHit], *, tenant_id: str, max_items: int) -> EvidenceSelection:
    """Tenant-filter, reject injected content, and fail closed on equal conflicts.

    ``metadata.claim_key`` is the canonical conflict identity supplied by
    ingestion (for example ``formula:yv-frag-010``).  Unequal authorities are
    resolved by provenance; equal-authority contradictory values are removed.
    Documents without a claim key remain independently citable.
    """
    allowed: list[SearchHit] = []
    rejected = 0
    for hit in hits:
        metadata = hit.metadata or {}
        source_tenant = str(metadata.get("tenant_id") or "public")
        if source_tenant not in {"public", tenant_id}:
            continue
        if contains_prompt_injection(hit.content, metadata):
            rejected += 1
            continue
        allowed.append(hit)

    grouped: dict[str, list[SearchHit]] = defaultdict(list)
    unkeyed: list[SearchHit] = []
    for hit in allowed:
        key = str((hit.metadata or {}).get("claim_key") or "").strip()
        if key:
            grouped[key].append(hit)
        else:
            unkeyed.append(hit)

    chosen = list(unkeyed)
    conflicts: list[str] = []
    for key, candidates in grouped.items():
        by_content: dict[str, list[SearchHit]] = defaultdict(list)
        for hit in candidates:
            by_content[" ".join(hit.content.lower().split())].append(hit)
        if len(by_content) == 1:
            chosen.append(max(candidates, key=lambda hit: (_TRUST_RANK.get(hit.trust_level, 0), hit.similarity)))
            continue
        ranked = sorted(
            candidates,
            key=lambda hit: (_TRUST_RANK.get(hit.trust_level, 0), hit.similarity),
            reverse=True,
        )
        if len(ranked) > 1 and _TRUST_RANK.get(ranked[0].trust_level, 0) == _TRUST_RANK.get(ranked[1].trust_level, 0):
            conflicts.append(key)
            continue
        chosen.append(ranked[0])

    chosen.sort(key=lambda hit: (-hit.similarity, str(hit.chunk_id)))
    return EvidenceSelection(hits=chosen[:max_items], conflicts=sorted(conflicts), rejected_injection=rejected)


def compact_context(chunks: list[dict[str, Any]], *, max_chars: int, max_chunks: int = 4) -> list[dict[str, Any]]:
    """Bound model context without silently changing which evidence was used."""
    remaining = max_chars
    compacted: list[dict[str, Any]] = []
    for chunk in chunks[:max_chunks]:
        # Do not add a useless fragment merely because a few characters remain.
        if remaining < 24:
            break
        copy = dict(chunk)
        content = str(copy.get("content") or "").strip()
        # Preserve whole text when possible; otherwise stop at a word boundary.
        if len(content) > remaining:
            content = content[: remaining - 1].rsplit(" ", 1)[0].strip() + "…"
        if not content:
            continue
        copy["content"] = content
        compacted.append(copy)
        remaining -= len(content)
    return compacted
