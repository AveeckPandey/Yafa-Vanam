"""Claim-safety: unverified/mock data can never surface as customer fact.

Covers the explicit spec §26 list: mock INCI, mock stability testing, mock SPF
results, mock ophthalmological testing, mock wear claims, visual-estimate
colour presented as measured laboratory colour, and legacy-concept ingredients
presented as final production formula.
"""

from __future__ import annotations

from app.rag.chunker import build_chunks, build_document
from app.rag.models import TrustLevel
from app.rag.repository import SearchHit
from app.rag.source_policy import can_surface_as_customer_fact


def hit(**overrides) -> SearchHit:
    """A well-formed AUTHORITATIVE hit, overridden per test."""
    fields = dict(
        chunk_id="c1", product_id="yv-test-001", product_name="Test", category=None,
        subcategory=None, product_type=None, chunk_type="product_overview",
        content="Test overview.", similarity=0.9,
        trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE.value,
        customer_factual_eligible=True, requires_qualification=False, metadata={},
    )
    fields.update(overrides)
    return SearchHit(**fields)


class TestCentralGateMatrix:
    """can_surface_as_customer_fact must reject every marker, at any depth."""

    def test_accepts_clean_metadata(self):
        assert can_surface_as_customer_fact({"topics": ["mascara"], "records": [{"name": "x"}]})

    def test_rejects_consumer_claim_not_allowed(self):
        assert not can_surface_as_customer_fact({"consumer_claim_allowed": False})

    def test_rejects_unverified_production(self):
        assert not can_surface_as_customer_fact({"production_verified": False})

    def test_rejects_unverified_formula(self):
        assert not can_surface_as_customer_fact(
            {"records": [{"name": "Niacinamide", "verified_for_final_formula": False}]}
        )

    def test_rejects_mock_verification_status(self):
        assert not can_surface_as_customer_fact({"verification_status": "mock"})

    def test_rejects_pending_verification_status(self):
        assert not can_surface_as_customer_fact({"verification_status": "pending"})

    def test_rejects_not_validated_claims(self):
        assert not can_surface_as_customer_fact({"claim_status": "not_validated"})

    def test_rejects_exclude_policy_marker(self):
        assert not can_surface_as_customer_fact({"mock_data_rag_policy": "exclude_from_factual_answers"})

    def test_rejects_deeply_nested_marker(self):
        metadata = {"evidence": {"claims": [{"sources": [{"verification_status": "development_only"}]}]}}
        assert not can_surface_as_customer_fact(metadata)

    def test_non_dict_input_is_rejected(self):
        assert can_surface_as_customer_fact(None) is False
        assert can_surface_as_customer_fact("clean") is False


class TestMockDataIngestion:
    def _chunk_by_local_key(self, chunks, needle):
        return next(chunk for chunk in chunks if needle in chunk.content.lower())

    def test_mock_inci_never_becomes_final_inci(self):
        product = {
            "id": "yv-mock-001", "name": "Mock Serum", "brand": "YAFA VANAM",
            "ingredients": {
                "active_ingredients": [{
                    "name": "Niacinamide", "role": "Brightening concept.",
                    "concentration": "10%",  # planning number, never verified
                    "source": "legacy_concept",
                    "verified_for_final_formula": False,
                    "verification_status": "mock",
                }],
            },
            "rag": {"enabled": True},
        }
        chunks = build_chunks(product)
        concept = next(c for c in chunks if c.chunk_type == "ingredients_concept")
        assert concept.customer_factual_eligible is False
        assert concept.trust_level == TrustLevel.LEGACY_CONCEPT
        assert "10%" in concept.content  # present but flagged non-factual
        assert can_surface_as_customer_fact(concept.metadata) is False

    def test_verified_ingredient_would_be_factual(self):
        """The counterfactual: a genuinely verified record stays surfaceable."""
        product = {
            "id": "yv-ver-001", "name": "Verified Balm", "brand": "YAFA VANAM",
            "ingredients": {
                "active_ingredients": [{
                    "name": "Glycerin", "role": "Humectant.",
                    "source": "manufacturer_specification",
                    "verified_for_final_formula": True,
                }],
            },
            "rag": {"enabled": True},
        }
        chunks = build_chunks(product)
        ingredients = [c for c in chunks if c.chunk_type == "ingredients"]
        assert ingredients, "verified records produce an 'ingredients' (not concept) chunk"
        assert ingredients[0].customer_factual_eligible is True
        assert ingredients[0].trust_level == TrustLevel.VERIFIED

    def test_mock_stability_test_stays_in_guardrails(self):
        product = {
            "id": "yv-mock-002", "name": "Mock Cream", "brand": "YAFA VANAM",
            "claims_review": {
                "status": "requires_formula_and_regulatory_review",
                "stability_test": {"result": "pass", "verification_status": "mock"},
            },
            "rag": {"enabled": True},
        }
        document = build_document(product, "Product.json")
        # Preserved for internal development use...
        assert document["guardrails"]["claims_review"]["stability_test"]["result"] == "pass"
        joined = " ".join(c.content.lower() for c in build_chunks(product))
        assert "stability" not in joined, "mock stability results must not become knowledge content"

    def test_mock_spf_result_is_never_real_spf_proof(self):
        product = {
            "id": "yv-mock-003", "name": "Mock Day Fluid", "brand": "YAFA VANAM",
            "sun_protection": {
                "intended_claim": {"spf": 30},
                "claim_status": "not_validated",
                "spf_test": {"method": None, "result": None, "verification_status": "mock"},
            },
            "rag": {"enabled": True},
        }
        document = build_document(product, "Product.json")
        assert document["guardrails"]["sun_protection"]["claim_status"] == "not_validated"
        joined = " ".join(c.content.lower() for c in build_chunks(product))
        assert "spf test" not in joined
        assert "spf 30 is proven" not in joined

    def test_mock_ophthalmological_testing_not_asserted(self):
        product = {
            "id": "yv-mock-004", "name": "Mock Mascara", "brand": "YAFA VANAM",
            "eye_safety": {
                "ophthalmological_test": {"performed": True, "report": "MOCK-1"},
                "ophthalmological_tested": False,
                "colourants_verified": False,
                "status": "requires_final_formula_and_regulatory_review",
            },
            "rag": {"enabled": True},
        }
        document = build_document(product, "Product.json")
        assert document["guardrails"]["eye_safety"]["ophthalmological_test"]["report"] == "MOCK-1"
        joined = " ".join(c.content.lower() for c in build_chunks(product))
        assert "ophthalmologist" not in joined
        assert "eye-safety tested" not in joined

    def test_mock_wear_claim_not_asserted(self):
        product = {
            "id": "yv-mock-005", "name": "Mock Lipstick", "brand": "YAFA VANAM",
            "makeup_profile": {
                "wear_claim": "12_hour_wear",
                "wear_claim_tested": False,
            },
            "rag": {"enabled": True},
        }
        document = build_document(product, "Product.json")
        assert document["guardrails"]["makeup_profile"]["wear_claim"] == "12_hour_wear"
        joined = " ".join(c.content.lower() for c in build_chunks(product))
        assert "12 hour wear" not in joined and "12-hour wear" not in joined

    def test_visual_estimate_colour_never_measured_lab_colour(self):
        """Hex values stay out of content entirely; the metadata note states
        they are indicative digital representations only."""
        product = {
            "id": "yv-mock-006", "name": "Mock Blush", "brand": "YAFA VANAM",
            "variants": [
                {"id": "v1", "shade": {"name": "Rose Petal", "hex": "#E8B4B8"}},
            ],
            "rag": {"enabled": True},
        }
        shade = next(c for c in build_chunks(product) if c.chunk_type == "shade_information")
        assert "Rose Petal" in shade.content
        assert "#e8b4b8" not in shade.content.lower()
        assert "not laboratory-measured" in shade.metadata["hex_note"]
