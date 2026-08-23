"""Chunker semantics: sections, provenance, stable identity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.chunker import (
    SemanticChunk,
    build_chunks,
    build_document,
    extract_aliases,
)
from app.rag.models import TrustLevel
from app.rag.normalizer import normalize_text
from app.rag.source_policy import can_surface_as_customer_fact

CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "processed" / "Product.json"


def load_product(product_id: str) -> dict:
    products = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return next(product for product in products if product["id"] == product_id)


@pytest.fixture(scope="module")
def mascara_chunks() -> list[SemanticChunk]:
    return build_chunks(load_product("yv-eye-001"))


@pytest.fixture(scope="module")
def fragrance_chunks() -> list[SemanticChunk]:
    return build_chunks(load_product("yv-frag-010"))


def by_type(chunks: list[SemanticChunk], chunk_type: str) -> list[SemanticChunk]:
    return [chunk for chunk in chunks if chunk.chunk_type == chunk_type]


class TestSectionCoverage:
    def test_core_sections_present(self, mascara_chunks):
        types = {chunk.chunk_type for chunk in mascara_chunks}
        # 'compatibility' is optional: this product only carries a schema
        # placeholder there, which the chunker deliberately drops.
        assert {
            "product_overview", "benefits", "usage", "warnings",
            "ingredients_concept", "evidence", "faq", "shade_information",
            "routine_position",
        } <= types

    def test_placeholder_compatibility_data_produces_no_chunk(self):
        base = {
            "id": "yv-test-002", "name": "Test Product", "brand": "YAFA VANAM",
            "compatibility": {"works_well_with": ["compatible_makeup_products"], "special_notes": []},
            "rag": {"enabled": True},
        }
        assert not [c for c in build_chunks(base) if c.chunk_type == "compatibility"]

    def test_chunks_are_natural_language_not_json_blobs(self, mascara_chunks):
        for chunk in mascara_chunks:
            assert not chunk.content.lstrip().startswith(("{", "[")), chunk.chunk_type
            assert len(chunk.content) < 2000, f"{chunk.chunk_type} suspiciously large"

    def test_overview_names_the_product(self, mascara_chunks):
        overview = by_type(mascara_chunks, "product_overview")[0]
        assert "Fernwing Volume Mascara" in overview.content
        assert "YAFA VANAM" in overview.content

    def test_faq_uses_question_answer_shape(self, mascara_chunks):
        faq = by_type(mascara_chunks, "faq")
        assert faq
        assert all(chunk.content.startswith("Question:") for chunk in faq)

    def test_scent_profile_captured(self, fragrance_chunks):
        scent = by_type(fragrance_chunks, "scent_profile")[0]
        assert "Top notes" in scent.content
        assert "Saffron" in scent.content


class TestProvenanceAndTrust:
    def test_catalogue_sections_are_authoritative_and_eligible(self, mascara_chunks):
        for chunk_type in ("product_overview", "benefits", "usage", "warnings", "faq"):
            for chunk in by_type(mascara_chunks, chunk_type):
                assert chunk.trust_level == TrustLevel.AUTHORITATIVE_CATALOGUE
                assert chunk.customer_factual_eligible is True
                assert chunk.requires_qualification is False

    def test_concept_ingredients_are_legacy_and_ineligible(self, mascara_chunks):
        concept = by_type(mascara_chunks, "ingredients_concept")
        assert concept, "mascara should produce concept ingredient chunks"
        for chunk in concept:
            assert chunk.trust_level == TrustLevel.LEGACY_CONCEPT
            assert chunk.customer_factual_eligible is False
            assert chunk.requires_qualification is True
            # The honesty qualifier lives in the content itself (spec §5).
            assert "NOT confirmed" in chunk.content
            # Raw provenance survives in metadata for defense in depth.
            assert all(record["verified_for_final_formula"] is False for record in chunk.metadata["records"])

    def test_evidence_is_qualified_ingredient_level(self, mascara_chunks):
        evidence = by_type(mascara_chunks, "evidence")
        assert evidence
        for chunk in evidence:
            assert chunk.trust_level == TrustLevel.RESEARCHED_QUALIFIED
            assert chunk.requires_qualification is True
            assert "does not prove the final" in chunk.content
            assert chunk.metadata["scope"] == "ingredient_level"
            assert chunk.metadata["claim_id"]
            assert chunk.metadata["avoid_without_product_substantiation"]

    def test_scent_copy_is_brand_confirmed(self, fragrance_chunks):
        scent = by_type(fragrance_chunks, "scent_profile")[0]
        assert scent.trust_level == TrustLevel.BRAND_CONFIRMED
        assert scent.customer_factual_eligible is True

    def test_eligible_metadata_always_passes_central_gate(self):
        """Invariant over the entire catalogue: no eligible chunk carries
        metadata that the centralized gate rejects."""
        products = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        for product in products:
            for chunk in build_chunks(product):
                if chunk.customer_factual_eligible:
                    assert can_surface_as_customer_fact(chunk.metadata), (
                        f"{product['id']}/{chunk.chunk_type}/{chunk.local_key} fails the gate"
                    )


class TestShadeInformation:
    def test_shade_names_in_content_hex_only_in_metadata(self, mascara_chunks):
        shade = by_type(mascara_chunks, "shade_information")[0]
        assert "Jet Black" in shade.content
        # Hex codes must never be presented as measured colour (spec §26).
        assert "#" not in shade.content
        assert shade.metadata["hex_note"]
        assert any(shade["hex"] for shade in shade.metadata["shades"])

    def test_variant_regulatory_rows_stay_out_of_eligible_metadata(self, mascara_chunks):
        shade = by_type(mascara_chunks, "shade_information")[0]
        assert "regulatory" not in json.dumps(shade.metadata)


class TestStableIdentity:
    def test_ids_are_deterministic(self, mascara_chunks):
        versions = {build_document(load_product("yv-eye-001"), "Product.json")["source_version"]}
        version = versions.pop()
        first = [chunk.stable_id(version) for chunk in mascara_chunks]
        rebuilt = [chunk.stable_id(version) for chunk in build_chunks(load_product("yv-eye-001"))]
        assert first == rebuilt

    def test_same_type_multiple_chunks_get_distinct_ids(self, mascara_chunks):
        version = "test-version"
        faq_ids = [chunk.stable_id(version) for chunk in by_type(mascara_chunks, "faq")]
        assert len(faq_ids) == len(set(faq_ids))

    def test_content_change_changes_identity(self):
        base = {
            "id": "yv-test-001", "name": "Test Product", "brand": "YAFA VANAM",
            "category": "Makeup", "subcategory": "Eyes", "product_type": "Mascara",
            "description": {"full": "Original description."},
            "rag": {"enabled": True},
        }
        original = build_chunks(base)[0]
        mutated = dict(base)
        mutated["description"] = {"full": "Rewritten description."}
        changed = build_chunks(mutated)[0]
        assert original.stable_id("v1") != changed.stable_id("v1")


class TestAliases:
    def test_exact_names_flagged(self):
        aliases = dict((normalized, exact) for _, normalized, exact in extract_aliases(load_product("yv-eye-001")))
        assert aliases.get("fernwing volume mascara") is True
        assert aliases.get("yafa vanam fernwing volume mascara") is True

    def test_generic_aliases_not_exact(self):
        aliases = dict((normalized, exact) for _, normalized, exact in extract_aliases(load_product("yv-eye-001")))
        assert aliases.get("mascara") is False

    def test_soft_ember_alias_exists(self):
        normalized_aliases = {normalized for _, normalized, _ in extract_aliases(load_product("yv-frag-010"))}
        assert "soft ember warm fragrance concept" in normalized_aliases


class TestDocumentPayload:
    def test_versions_preserved(self):
        document = build_document(load_product("yv-eye-001"), "Product.json")
        assert document["source_version"] == "2.0-post-research-draft"
        assert document["data_version"] == "2.0-post-research-draft"
        assert document["source_file"] == "Product.json"

    def test_policy_structured_metadata_retained(self):
        document = build_document(load_product("yv-eye-001"), "Product.json")
        assert document["answer_policy"]["formula_specific_claim"] == "require_verified_formula_or_test"
        assert "pregnancy and retinoids" in document["citation_required_topics"]
        assert "eye injury" in document["medical_escalation_topics"]

    def test_guardrail_sections_preserved_but_out_of_chunks(self):
        product = load_product("yv-skin-020")  # sunscreen with unvalidated SPF claims
        document = build_document(product, "Product.json")
        assert document["guardrails"]["sun_protection"]["claim_status"] == "not_validated"

    def test_unvalidated_spf_never_asserted_as_proof(self):
        """The product name contains 'SPF 50' (identity is fine); what must
        never appear is performance/proof language for the unvalidated claim."""
        product = load_product("yv-skin-020")
        joined = normalize_text(" ".join(c.content for c in build_chunks(product))).lower()
        # Only unambiguous proof language; phrases like 'final validated spf
        # testing' legitimately appear in forward-looking label directions.
        for forbidden in ("proven", "clinically", "dermatologically tested", "guaranteed"):
            assert forbidden not in joined, forbidden
        # The catalogue's own honesty qualifier survives into knowledge content.
        overview = next(c for c in build_chunks(product) if c.chunk_type == "product_overview")
        assert "not treated as validated" in overview.content.lower()
