"""Semantic chunking of canonical catalogue records.

One product becomes many independently retrievable chunks (overview, benefits,
usage, warnings, ingredient concepts, evidence claims, FAQ, shades, scent,
compatibility, routine). Chunks are natural-language text -- never serialized
JSON blobs -- and every chunk carries its provenance/trust classification so
the retrieval layer can enforce claim policy downstream.

Metadata hygiene rule: chunks marked customer_factual_eligible must not carry
nested records that would fail source_policy.can_surface_as_customer_fact
(e.g. variant regulatory rows with pending reviews). Verification-pending
sections (eye_safety, sun_protection, makeup_profile, ...) are preserved on
the document-level guardrails payload instead of inside eligible chunks.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.rag.models import ChunkType, TrustLevel
from app.rag.normalizer import content_hash, normalize_text, stable_document_id
from app.rag.source_policy import derive_trust_level, requires_qualification

# Sections whose entire purpose is development/verification tracking. They are
# preserved as structured document guardrails and never become customer facts.
_GUARDRAIL_SECTIONS = (
    "eye_safety",
    "sun_protection",
    "makeup_profile",
    "claims_review",
    "research_gaps",
)


@dataclass(frozen=True)
class SemanticChunk:
    """One retrievable unit of product knowledge."""

    canonical_product_id: str
    chunk_type: str
    local_key: str  # disambiguates multiple chunks of the same type (claim_id, question...)
    content: str
    trust_level: TrustLevel
    customer_factual_eligible: bool
    requires_qualification: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_hash(self) -> str:
        return content_hash(self.content)

    def stable_id(self, source_version: str) -> str:
        from app.rag.normalizer import stable_chunk_id

        type_key = self.chunk_type if not self.local_key else f"{self.chunk_type}#{self.local_key}"
        return stable_chunk_id(self.canonical_product_id, type_key, source_version, self.source_hash)


def _clean(value: Any) -> str:
    return normalize_text(value)


def _bullets(items: list[Any] | None) -> list[str]:
    return [_clean(item) for item in (items or []) if _clean(item)]


_PLACEHOLDER = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)+$")


def _real_items(items: list[Any] | None) -> list[str]:
    """Bullet texts minus snake_case schema placeholders like 'compatible_makeup_products'."""
    return [item for item in _bullets(items) if not _PLACEHOLDER.match(item)]


def _join_bullets(header: str, items: list[str]) -> str:
    return header + "\n" + "\n".join(f"- {item}" for item in items)


def build_source_version(product: dict[str, Any]) -> str:
    rag = product.get("rag") or {}
    meta = product.get("metadata") or {}
    return _clean(rag.get("source_version")) or _clean(meta.get("data_version")) or "unknown"


def build_document(product: dict[str, Any], source_file: str) -> dict[str, Any]:
    """Flatten the catalogue record into a rag_documents row payload."""
    rag = product.get("rag") or {}
    meta = product.get("metadata") or {}
    guardrails: dict[str, Any] = {}
    for section in _GUARDRAIL_SECTIONS:
        if product.get(section) is not None:
            guardrails[section] = product[section]
    fragrance = product.get("fragrance_profile") or {}
    for key in ("performance_claims", "formula_validation"):
        if fragrance.get(key) is not None:
            # Wear/performance numbers stay out of knowledge content until tested.
            guardrails[f"fragrance_{key}"] = fragrance[key]
    if product.get("live_data_contract") is not None:
        guardrails["live_data_contract"] = product["live_data_contract"]
    evidence_note = _clean((product.get("evidence") or {}).get("note"))
    if evidence_note:
        guardrails["evidence_note"] = evidence_note

    return {
        "id": stable_document_id(product["id"]),
        "canonical_product_id": product["id"],
        "product_name": _clean(product.get("name")),
        "category": _clean(product.get("category")) or None,
        "subcategory": _clean(product.get("subcategory")) or None,
        "product_type": _clean(product.get("product_type")) or None,
        "source_file": source_file,
        "source_version": build_source_version(product),
        "data_version": _clean(meta.get("data_version")) or None,
        "answer_policy": rag.get("answer_policy") or {},
        "citation_required_topics": rag.get("citation_required_topics") or [],
        "medical_escalation_topics": rag.get("medical_escalation_topics") or [],
        "guardrails": guardrails,
    }


def extract_aliases(product: dict[str, Any]) -> list[tuple[str, str, bool]]:
    """(alias, normalized_alias, is_exact_name) triples for alias resolution.

    Only names identify a product; generic aliases ("mascara", category words
    shared by many products) are stored as non-exact so the retriever can treat
    multi-product matches as ambiguous instead of pinning one product.
    """
    from app.rag.normalizer import normalize_alias

    name = _clean(product.get("name"))
    brand = _clean(product.get("brand"))
    exact_names = {normalize_alias(name)}
    if brand and brand != name:
        exact_names.add(normalize_alias(f"{brand} {name}"))

    aliases: dict[str, tuple[str, str, bool]] = {}
    def add(alias: str, is_exact: bool) -> None:
        cleaned = _clean(alias)
        normalized = normalize_alias(cleaned)
        if not normalized:
            return
        exact = is_exact or normalized in exact_names
        existing = aliases.get(normalized)
        if existing is None or (exact and not existing[2]):
            aliases[normalized] = (cleaned, normalized, exact)

    add(name, True)
    if brand and brand != name:
        add(f"{brand} {name}", True)
    for alias in (product.get("rag") or {}).get("search_aliases") or []:
        add(str(alias), False)
    return sorted(aliases.values(), key=lambda item: item[1])


def build_chunks(product: dict[str, Any]) -> list[SemanticChunk]:
    """Generate all semantic chunks for one catalogue product."""
    product_id = product["id"]
    name = _clean(product.get("name"))
    brand = _clean(product.get("brand")) or "YAFA VANAM"
    rag = product.get("rag") or {}

    chunks: list[SemanticChunk] = []

    def emit(
        chunk_type: ChunkType | str,
        content: str,
        trust: TrustLevel,
        *,
        eligible: bool,
        qualified: bool | None = None,
        local_key: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        content = normalize_text(content)
        if not content:
            return
        chunks.append(
            SemanticChunk(
                canonical_product_id=product_id,
                chunk_type=chunk_type.value if isinstance(chunk_type, ChunkType) else chunk_type,
                local_key=local_key,
                content=content,
                trust_level=trust,
                customer_factual_eligible=eligible,
                requires_qualification=requires_qualification(trust) if qualified is None else qualified,
                metadata=metadata or {},
            )
        )

    # -- product_overview ---------------------------------------------------
    description = product.get("description") or {}
    overview_lines = [f"{name} is a {product.get('product_type') or 'product'} by {brand} "
                      f"in the {_clean(product.get('category')) or 'beauty'} / "
                      f"{_clean(product.get('subcategory')) or 'general'} range."]
    full = _clean(description.get("full")) or _clean(description.get("short"))
    if full:
        overview_lines.append(full)
    topics = _bullets(rag.get("topics"))
    if topics:
        overview_lines.append("Commonly searched as: " + ", ".join(topics[:6]) + ".")
    emit(
        ChunkType.PRODUCT_OVERVIEW,
        "\n".join(overview_lines),
        TrustLevel.AUTHORITATIVE_CATALOGUE,
        eligible=True,
        metadata={
            "slug": _clean(product.get("slug")) or None,
            "status": _clean(product.get("status")) or None,
            "topics": topics,
            "suggested_questions": _bullets(rag.get("suggested_questions")),
        },
    )

    # -- benefits ------------------------------------------------------------
    benefits = _bullets(product.get("benefits"))
    if benefits:
        emit(
            ChunkType.BENEFITS,
            _join_bullets(f"What {name} is designed to do:", benefits),
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
        )

    # -- usage ----------------------------------------------------------------
    usage = product.get("usage") or {}
    usage_bits = []
    how_to = _clean(usage.get("how_to_use"))
    if how_to:
        usage_bits.append(how_to)
    amount = _clean(usage.get("amount"))
    if amount:
        usage_bits.append(f"Typical amount: {amount}.")
    when = _bullets(usage.get("when"))
    if when:
        usage_bits.append("Time of use: " + ", ".join(when) + ".")
    if usage_bits:
        emit(
            ChunkType.USAGE,
            f"How to use {name}:\n" + " ".join(usage_bits),
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
        )

    # -- warnings -------------------------------------------------------------
    warnings = _bullets(product.get("warnings"))
    if warnings:
        emit(
            ChunkType.WARNINGS,
            _join_bullets(f"Safety notes for {name}:", warnings),
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
        )

    # -- ingredients ----------------------------------------------------------
    chunks.extend(_ingredient_chunks(product_id, name, product))

    # -- evidence ---------------------------------------------------------------
    chunks.extend(_evidence_chunks(product_id, name, product))

    # -- faq ----------------------------------------------------------------------
    for index, entry in enumerate(rag.get("customer_questions") or []):
        question = _clean(entry.get("question"))
        answer = _clean(entry.get("answer"))
        if not question or not answer:
            continue
        emit(
            ChunkType.FAQ,
            f"Question: {question}\nAnswer: {answer}",
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
            local_key=f"q{index}",
            metadata={"question": question},
        )

    # -- shade_information ---------------------------------------------------------
    shade_rows = [
        {
            "name": _clean(variant.get("shade", {}).get("name")),
            "hex": _clean(variant.get("shade", {}).get("hex")) or None,
        }
        for variant in product.get("variants") or []
        if isinstance(variant, dict) and isinstance(variant.get("shade"), dict) and _clean(variant["shade"].get("name"))
    ]
    if shade_rows:
        seen: set[str] = set()
        unique_shades = [row for row in shade_rows if not (row["name"] in seen or seen.add(row["name"]))]
        emit(
            ChunkType.SHADE_INFORMATION,
            f"{name} is available in these shades: " + ", ".join(row["name"] for row in unique_shades) + ".",
            # Authoritative shade names come from the catalogue's verified variant list.
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
            metadata={
                "shades": unique_shades,
                # Hex swatches are indicative screen values, never measured colour data.
                "hex_note": "Hex values are indicative digital representations, not laboratory-measured colour.",
                "shade_system": product.get("shade_system"),
            },
        )

    # -- scent_profile -----------------------------------------------------------
    chunks.extend(_scent_chunks(product_id, name, brand, product))

    # -- compatibility --------------------------------------------------------------
    compatibility = product.get("compatibility") or {}
    pairs_well = _real_items(compatibility.get("works_well_with"))
    special_notes = _real_items(compatibility.get("special_notes"))
    if pairs_well or special_notes:
        lines = []
        if pairs_well:
            lines.append(_join_bullets(f"{name} works well with:", pairs_well))
        if special_notes:
            lines.append(_join_bullets("Compatibility notes:", special_notes))
        emit(
            ChunkType.COMPATIBILITY,
            "\n".join(lines),
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
        )

    # -- routine_position --------------------------------------------------------
    routine = ((product.get("recommendation_profile") or {}).get("routine")) or {}
    routine_bits = []
    step = _clean(routine.get("step"))
    if step:
        routine_bits.append(f"{name} sits at the '{step}' step of a routine.")
    frequency = _clean(routine.get("frequency"))
    if frequency:
        routine_bits.append(f"Suggested frequency: {frequency.replace('_', ' ')}.")
    times = _bullets(routine.get("time"))
    if times:
        routine_bits.append("Routine timing: " + ", ".join(times) + ".")
    if routine_bits:
        emit(
            ChunkType.ROUTINE_POSITION,
            " ".join(routine_bits),
            TrustLevel.AUTHORITATIVE_CATALOGUE,
            eligible=True,
            metadata={"routine_step": step or None},
        )

    return chunks


def _ingredient_chunks(product_id: str, name: str, product: dict[str, Any]) -> list[SemanticChunk]:
    """Split ingredients by derived trust so concept data can never masquerade
    as confirmed formula information."""
    ingredients = product.get("ingredients") or {}
    records = list(ingredients.get("active_ingredients") or []) + list(ingredients.get("base_ingredients") or [])
    chunks: list[SemanticChunk] = []

    by_trust: dict[TrustLevel, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict) or not _clean(record.get("name")):
            continue
        by_trust[derive_trust_level("ingredients", record)].append(record)

    for trust, group in by_trust.items():
        is_concept = trust in (TrustLevel.LEGACY_CONCEPT, TrustLevel.MOCK_DEVELOPMENT, TrustLevel.PENDING_VERIFICATION)
        if is_concept:
            header = (
                f"Ingredient concepts for {name} (planning stage only - NOT confirmed as the "
                f"final production formula):"
            )
            chunk_type = ChunkType.INGREDIENTS_CONCEPT
        else:
            header = f"Ingredients of {name}:"
            chunk_type = ChunkType.INGREDIENTS
        lines = [header]
        slim_records = []
        for record in group:
            role = _clean(record.get("role"))
            concentration = _clean(record.get("concentration"))
            label = _clean(record.get("name"))
            suffix = f" ({concentration})" if concentration else ""
            lines.append(f"- {label}{suffix}: {role}." if role else f"- {label}{suffix}.")
            slim_records.append(
                {
                    "name": label,
                    "role": role,
                    "concentration": concentration or None,
                    "source": _clean(record.get("source")) or None,
                    "verified_for_final_formula": record.get("verified_for_final_formula"),
                }
            )
        note = _clean(ingredients.get("ingredient_data_note"))
        if note and is_concept:
            lines.append(note)
        chunks.append(
            SemanticChunk(
                canonical_product_id=product_id,
                chunk_type=chunk_type.value,
                local_key=trust.value.lower(),
                content="\n".join(lines),
                trust_level=trust,
                customer_factual_eligible=not is_concept,
                requires_qualification=is_concept,
                # Keep the raw provenance flags here: even if the row flag were
                # flipped later, can_surface_as_customer_fact still rejects it.
                metadata={"records": slim_records, "ingredient_data_note": note or None},
            )
        )

    full_inci = _clean(ingredients.get("full_inci"))
    if full_inci:
        chunks.append(
            SemanticChunk(
                canonical_product_id=product_id,
                chunk_type=ChunkType.INGREDIENTS.value,
                local_key="inci",
                content=f"Full INCI (label ingredient list) of {name}: {full_inci}",
                trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE,
                customer_factual_eligible=True,
                metadata={"full_inci": True},
            )
        )
    return chunks


def _evidence_chunks(product_id: str, name: str, product: dict[str, Any]) -> list[SemanticChunk]:
    """One chunk per research claim, always carrying the ingredient-level scope
    qualifier so ingredient science is never presented as final-product proof."""
    evidence = product.get("evidence") or {}
    chunks: list[SemanticChunk] = []
    for claim in evidence.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        claim_text = _clean(claim.get("claim_text"))
        ingredient = _clean(claim.get("ingredient"))
        if not claim_text:
            continue
        applicability = _clean(claim.get("applicability_to_final_product"))
        lines = [f"Ingredient research ({ingredient}): {claim_text}"]
        allowed_wording = _bullets(claim.get("allowed_consumer_wording"))
        if allowed_wording:
            lines.append("Allowed consumer wording: " + "; ".join(allowed_wording) + ".")
        avoid = _bullets(claim.get("avoid_without_product_substantiation"))
        if avoid:
            lines.append("Do NOT claim without product substantiation: " + "; ".join(avoid) + ".")
        lines.append(
            "Scope: ingredient-level evidence - this does not prove the final "
            f"{name} formula (applicability: {applicability or 'requires confirmation'})."
        )
        chunks.append(
            SemanticChunk(
                canonical_product_id=product_id,
                chunk_type=ChunkType.EVIDENCE.value,
                local_key=_clean(claim.get("claim_id")) or content_hash(claim_text)[:12],
                content="\n".join(lines),
                trust_level=derive_trust_level("evidence_claim", claim),
                customer_factual_eligible=True,
                requires_qualification=True,
                metadata={
                    "claim_id": _clean(claim.get("claim_id")) or None,
                    "ingredient": ingredient or None,
                    "scope": _clean(claim.get("scope")) or None,
                    "evidence_level": _clean(claim.get("evidence_level")) or None,
                    "applicability_to_final_product": applicability or None,
                    "allowed_consumer_wording": allowed_wording,
                    "avoid_without_product_substantiation": avoid,
                    "sources": claim.get("sources") or [],
                },
            )
        )
    return chunks


def _scent_chunks(product_id: str, name: str, brand: str, product: dict[str, Any]) -> list[SemanticChunk]:
    """Fragrance descriptions are the brand's own concept copy: surfaceable,
    but wear/performance numbers stay behind in document guardrails."""
    profile = product.get("fragrance_profile")
    if not isinstance(profile, dict):
        return []

    lines = [f"Scent profile of {name} ({brand}):"]
    family = _clean(profile.get("family"))
    if family:
        lines.append(f"Family: {family.replace('_', ' ')}.")
    facets = _bullets(profile.get("facets"))
    if facets:
        lines.append("Facets: " + ", ".join(facets) + ".")
    for label, key in (("Top notes", "top_notes"), ("Heart notes", "heart_notes"), ("Base notes", "base_notes"),
                       ("Signature notes", "signature_notes")):
        notes = _bullets(profile.get(key))
        if notes:
            lines.append(f"{label}: " + ", ".join(notes) + ".")
    character = _clean(profile.get("scent_character"))
    if character:
        lines.append(character)
    story = _clean(profile.get("scent_story"))
    if story:
        lines.append(story)
    mood = _bullets(profile.get("mood"))
    if mood:
        lines.append("Mood: " + ", ".join(mood) + ".")

    return [
        SemanticChunk(
            canonical_product_id=product_id,
            chunk_type=ChunkType.SCENT_PROFILE.value,
            local_key="brand_description",
            content="\n".join(lines),
            trust_level=derive_trust_level("brand_statement", profile),
            customer_factual_eligible=True,
            requires_qualification=False,
            metadata={
                "related_scent_line": _clean(profile.get("related_scent_line")) or None,
                "intensity_positioning": _clean(profile.get("intensity_positioning")) or None,
                "gender_positioning": _clean(profile.get("gender_positioning")) or None,
                "season": _bullets(profile.get("season")),
                "occasion": _bullets(profile.get("occasion")),
                "source_status": _clean(profile.get("source_status")) or None,
            },
        )
    ]
