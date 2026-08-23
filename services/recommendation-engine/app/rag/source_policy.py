"""Centralized provenance/trust policy for RAG content.

Every decision about whether a piece of ingested data may back a customer-facing
factual statement lives here. Do not duplicate this logic elsewhere.
"""

from __future__ import annotations

from typing import Any

from app.rag.models import TrustLevel

# Metadata keys/values that disqualify content from being surfaced as fact.
_DISQUALIFIERS: tuple[tuple[str, set[Any]], ...] = (
    ("consumer_claim_allowed", {False}),
    ("production_verified", {False}),
    ("verified_for_final_formula", {False}),
    ("brand_confirmed", {False}),
)

_MOCK_VERIFICATION_STATUSES = {
    "mock", "unverified", "pending", "pending_verification", "development_only",
    "not_validated",  # e.g. sun_protection.claim_status before SPF testing
}

# Keys carrying one of the statuses above wherever they appear in metadata.
_STATUS_KEYS = ("verification_status", "claim_status", "reference_status")

_EXCLUDE_POLICIES = {"exclude_from_factual_answers", "internal_only", "do_not_surface"}

# Trust levels whose statements always need an explicit qualifier when shown.
_QUALIFICATION_REQUIRED = {
    TrustLevel.RESEARCHED_QUALIFIED,
    TrustLevel.LEGACY_CONCEPT,
    TrustLevel.INFERRED_AESTHETIC,
    TrustLevel.VISUAL_ESTIMATE,
    TrustLevel.PENDING_VERIFICATION,
    TrustLevel.MOCK_DEVELOPMENT,
}


def _iter_metadata_values(metadata: dict[str, Any]) -> Any:
    """Yield metadata values plus one level of nesting (ingredient/evidence records)."""
    stack = [metadata]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(item for item in current if isinstance(item, (dict, list)))


def can_surface_as_customer_fact(metadata: dict[str, Any] | None) -> bool:
    """Single gate deciding whether content may back a customer factual answer.

    Rejects records carrying any unverified/mock marker, wherever it appears in
    the metadata tree (top level, ingredient records, evidence claims, etc.).
    """
    if not isinstance(metadata, dict):
        return False
    for node in _iter_metadata_values(metadata):
        if not isinstance(node, dict):
            continue
        policy = node.get("mock_data_rag_policy")
        if isinstance(policy, str) and policy.strip().lower() in _EXCLUDE_POLICIES:
            return False
        for status_key in _STATUS_KEYS:
            status = node.get(status_key)
            if isinstance(status, str) and status.strip().lower() in _MOCK_VERIFICATION_STATUSES:
                return False
        for key, rejected_values in _DISQUALIFIERS:
            value = node.get(key)
            if isinstance(value, bool) and value in rejected_values:
                return False
    return True


def requires_qualification(trust_level: TrustLevel) -> bool:
    """Whether statements from this trust level need explicit qualification."""
    return trust_level in _QUALIFICATION_REQUIRED


def derive_trust_level(source_kind: str, record: dict[str, Any] | None = None) -> TrustLevel:
    """Classify a product section's provenance into the common trust enum.

    source_kind values come from the chunker: catalogue_section, ingredients,
    evidence_claim, shade_swatch, recommendation_metadata, rag_faq, mock.
    """
    record = record or {}
    kind = source_kind.lower()

    if kind == "mock":
        return TrustLevel.MOCK_DEVELOPMENT
    if kind == "ingredients":
        sources = {str(record.get("source", "")).lower()}
        if record.get("verified_for_final_formula") is False or "legacy_concept" in sources:
            return TrustLevel.LEGACY_CONCEPT
        return TrustLevel.VERIFIED
    if kind == "evidence_claim":
        applicability = str(record.get("applicability_to_final_product", "")).lower()
        if "confirm" in applicability or "requires" in applicability:
            return TrustLevel.RESEARCHED_QUALIFIED
        return TrustLevel.RESEARCHED_QUALIFIED
    if kind == "shade_swatch":
        return TrustLevel.VISUAL_ESTIMATE
    if kind == "recommendation_metadata":
        return TrustLevel.INFERRED_AESTHETIC
    if kind == "brand_statement":
        return TrustLevel.BRAND_CONFIRMED

    # catalogue_section / rag_faq and anything unrecognized default to the
    # canonical catalogue's authority level.
    return TrustLevel.AUTHORITATIVE_CATALOGUE
