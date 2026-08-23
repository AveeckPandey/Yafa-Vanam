"""Retriever orchestration against stubbed repository + offline embedder.

Verifies spec §16 (alias resolution before vectors), §17 (PDP scoping of
"this"), §18 (global retrieval), §23 (response shape), §26 (customer mode
never surfaces ineligible chunks) and §27 (live-data deferral).
"""

from __future__ import annotations

import pytest

from app.rag.providers import HashingEmbeddingProvider
from app.rag.models import TrustLevel
from app.rag.repository import AliasMatch, SearchHit, _alias_match_rank
from app.rag.retriever import RagRetriever
from app.rag.schemas import PageContext, RagSearchRequest


def hit(product_id: str, chunk_type: str, content: str, similarity: float = 0.9, **overrides) -> SearchHit:
    fields = dict(
        chunk_id=f"{product_id}-{chunk_type}", product_id=product_id,
        product_name=product_id.upper(), category="Makeup", subcategory="Eyes",
        product_type="Mascara", chunk_type=chunk_type, content=content, similarity=similarity,
        trust_level=TrustLevel.AUTHORITATIVE_CATALOGUE.value,
        customer_factual_eligible=True, requires_qualification=False, metadata={},
    )
    fields.update(overrides)
    return SearchHit(**fields)


class StubRepo:
    """In-memory stand-in for RagRepository."""

    def __init__(self, hits: list[SearchHit], aliases: list[AliasMatch] | None = None,
                 document: dict | None = None) -> None:
        self.hits = hits
        self.aliases = aliases or []
        self.document = document
        self.search_calls: list[dict] = []

    def search(self, query_vector, *, product_ids=None, customer_factual_only=True, top_k=5,
               chunk_types=None, trust_levels=None):
        self.search_calls.append({
            "product_ids": product_ids, "customer_only": customer_factual_only,
            "top_k": top_k, "chunk_types": chunk_types, "trust_levels": trust_levels,
        })
        pool = list(self.hits)
        if product_ids:
            pool = [h for h in pool if h.product_id in set(product_ids)]
        if customer_factual_only:
            pool = [h for h in pool if h.customer_factual_eligible]
        return pool[:top_k]

    def resolve_aliases(self, normalized_query: str) -> list[AliasMatch]:
        return self.aliases

    def document_for_product(self, product_id: str) -> dict | None:
        return self.document


@pytest.fixture()
def retriever_factory():
    def build(repo: StubRepo) -> RagRetriever:
        return RagRetriever(repo, HashingEmbeddingProvider())
    return build


def make_request(query: str, **kwargs) -> RagSearchRequest:
    return RagSearchRequest(query=query, **kwargs)


class TestPageContextScoping:
    async def test_this_on_pdp_restricts_to_that_product(self, retriever_factory):
        repo = StubRepo([
            hit("yv-frag-010", "scent_profile", "Soft Ember scent: saffron, black tea, sandalwood."),
            hit("yv-eye-001", "scent_profile", "Fernwing has no scent story."),
        ])
        response = await retriever_factory(repo).search(make_request(
            "What does this smell like?",
            page_context=PageContext(type="product", product_id="yv-frag-010"),
        ))
        assert response.product_id == "yv-frag-010"
        assert response.resolution == "page_context"
        # "This" never triggers catalogue-wide retrieval.
        assert repo.search_calls[0]["product_ids"] == ["yv-frag-010"]
        assert {r.product_id for r in response.results} == {"yv-frag-010"}

    async def test_explicit_product_id_scopes_too(self, retriever_factory):
        repo = StubRepo([hit("yv-eye-001", "usage", "Apply from lash roots to tips.")])
        response = await retriever_factory(repo).search(make_request(
            "How do I use it?", product_id="yv-eye-001",
        ))
        assert response.resolution == "explicit_product_id"
        assert repo.search_calls[0]["product_ids"] == ["yv-eye-001"]


class TestAliasResolution:
    async def test_unique_alias_pins_product_before_vectors(self, retriever_factory):
        repo = StubRepo(
            [hit("yv-frag-010", "scent_profile", "Warm amber scent.")],
            aliases=[AliasMatch("yv-frag-010", "Soft Ember Warm Fragrance Concept", 1, 33)],
        )
        response = await retriever_factory(repo).search(make_request("What is the scent profile of Soft Ember?"))
        assert response.resolved_product_id == "yv-frag-010"
        assert response.resolution == "normalized_alias"
        assert repo.search_calls[0]["product_ids"] == ["yv-frag-010"]

    async def test_exact_alias_reported_as_exact(self, retriever_factory):
        repo = StubRepo(
            [hit("yv-eye-001", "product_overview", "Fernwing Volume Mascara overview.")],
            aliases=[AliasMatch("yv-eye-001", "fernwing volume mascara", 3, 23)],
        )
        response = await retriever_factory(repo).search(make_request("Fernwing Volume Mascara"))
        assert response.resolution == "exact_alias"

    async def test_ambiguous_alias_stays_catalogue_wide(self, retriever_factory):
        repo = StubRepo(
            [hit("yv-eye-001", "product_overview", "Fernwing mascara."), hit("yv-eye-002", "product_overview", "Lash Lift mascara.")],
            aliases=[
                AliasMatch("yv-eye-001", "mascara", 3, 7),
                AliasMatch("yv-eye-002", "mascara", 3, 7),
            ],
        )
        response = await retriever_factory(repo).search(make_request("mascara"))
        assert response.resolution == "ambiguous_alias"
        assert response.resolved_product_id is None
        assert repo.search_calls[0]["product_ids"] is None  # global retrieval intact

    async def test_no_alias_match_uses_vectors_globally(self, retriever_factory):
        repo = StubRepo([hit("yv-eye-001", "benefits", "Adds visible lash volume.")])
        response = await retriever_factory(repo).search(make_request("What products have a natural makeup positioning?"))
        assert response.resolution == "none"
        assert repo.search_calls[0]["product_ids"] is None
        assert response.results

    async def test_stronger_match_beats_weaker_competitor(self, retriever_factory):
        """A full-name mention pins its product even when another product's
        name merely extends a fragment of the same query."""
        repo = StubRepo(
            [hit("yv-frag-010", "scent_profile", "Warm amber scent.")],
            aliases=[
                AliasMatch("yv-frag-010", "soft ember warm fragrance concept", 2, 33),
                AliasMatch("yv-eye-002", "soft focus powder", 1, 17),
            ],
        )
        response = await retriever_factory(repo).search(
            make_request("What is Soft Ember Warm Fragrance Concept like?")
        )
        assert response.resolved_product_id == "yv-frag-010"
        assert repo.search_calls[0]["product_ids"] == ["yv-frag-010"]


class TestAliasMatchRanking:
    """Unit contract for repository._alias_match_rank (hermetic, no DB)."""

    def test_exact_equality(self):
        assert _alias_match_rank("fernwing volume mascara", "fernwing volume mascara", specific=True) == 3

    def test_whole_name_contained_mid_sentence(self):
        assert _alias_match_rank(
            "what is soft ember warm fragrance concept like",
            "soft ember warm fragrance concept", specific=True,
        ) == 2

    def test_partial_two_word_run_extends_to_full_name(self):
        assert _alias_match_rank(
            "what is the scent profile of soft ember",
            "soft ember warm fragrance concept", specific=True,
        ) == 1

    def test_distinctive_single_word_extends_to_full_name(self):
        assert _alias_match_rank("is fernwing waterproof", "fernwing volume mascara", specific=True) == 1

    def test_short_generic_word_pins_nothing(self):
        assert _alias_match_rank("something soft for summer", "soft ember warm fragrance concept", specific=True) == 0

    def test_substring_inside_larger_word_does_not_count(self):
        # "ember" inside "december" is not a product mention.
        assert _alias_match_rank("it lasted until december", "ember glow", specific=True) == 0

    def test_generic_single_word_alias_needs_prefix_or_equality(self):
        from app.rag.repository import _alias_is_specific

        specific = _alias_is_specific("mascara", is_exact_name=False)
        # Mid-sentence "mascara" must not count as naming one product...
        assert _alias_match_rank("best mascara for volume", "mascara", specific=specific) == 0
        # ...but equality and query-initial use still do (legacy behaviour).
        assert _alias_match_rank("mascara", "mascara", specific=specific) == 3

    def test_multi_word_generic_alias_is_still_specific(self):
        from app.rag.repository import _alias_is_specific

        assert _alias_is_specific("warm amber", is_exact_name=False) is True
        assert _alias_is_specific("soft ember warm fragrance concept", is_exact_name=True) is True
        assert _alias_is_specific("fragrance", is_exact_name=False) is False
        assert _alias_match_rank(
            "which warm amber should i try", "warm amber",
            specific=_alias_is_specific("warm amber", False),
        ) == 2


class TestPolicyEnforcement:
    async def test_customer_mode_drops_ineligible_hits(self, retriever_factory):
        repo = StubRepo([
            hit("yv-eye-001", "ingredients_concept", "Concept ingredients: niacinamide 10%.",
                trust_level=TrustLevel.LEGACY_CONCEPT.value,
                customer_factual_eligible=False, requires_qualification=True,
                metadata={"records": [{"verified_for_final_formula": False}]}),
            hit("yv-eye-001", "usage", "Apply from lash roots to tips."),
        ])
        response = await retriever_factory(repo).search(make_request("What is the INCI of this mascara?", product_id="yv-eye-001"))
        assert [r.chunk_type for r in response.results] == ["usage"]

    async def test_internal_mode_returns_flagged_ineligible_hits(self, retriever_factory):
        repo = StubRepo([
            hit("yv-eye-001", "ingredients_concept", "Concept ingredients.",
                trust_level=TrustLevel.LEGACY_CONCEPT.value,
                customer_factual_eligible=False, requires_qualification=True,
                metadata={"records": [{"verified_for_final_formula": False}]}),
        ])
        response = await retriever_factory(repo).search(make_request(
            "What is the INCI of this mascara?", product_id="yv-eye-001", allowed_for_customer=False,
        ))
        assert response.results and response.results[0].customer_factual_eligible is False

    async def test_gate_rejects_poisoned_metadata_even_with_eligible_flag(self, retriever_factory):
        """Defense in depth: a row flipped to eligible in the DB is still caught
        by the centralized metadata gate at retrieval time."""
        repo = StubRepo([
            hit("yv-eye-001", "ingredients", "Verified INCI: ...",
                customer_factual_eligible=True,  # tampered
                metadata={"verification_status": "mock"}),
        ])
        response = await retriever_factory(repo).search(make_request("INCI?", product_id="yv-eye-001"))
        assert response.results == []


class TestLiveDataDeferral:
    async def test_pure_inventory_question_suppresses_results(self, retriever_factory):
        repo = StubRepo([hit("yv-eye-001", "product_overview", "Fernwing overview.")])
        response = await retriever_factory(repo).search(make_request("Is this in stock?"))
        assert response.results == []
        assert [r.domain.value for r in response.requires_live_data] == ["inventory"]
        assert repo.search_calls == [], "no vector search should run for pure live-data questions"

    async def test_mixed_question_still_returns_knowledge(self, retriever_factory):
        repo = StubRepo([hit("yv-frag-010", "scent_profile", "Saffron and black tea over amber woods.")])
        response = await retriever_factory(repo).search(
            make_request("What does Soft Ember smell like and how much does it cost?")
        )
        assert response.results
        assert any(r.domain.value == "price" for r in response.requires_live_data)

    async def test_live_requirement_carries_reason(self, retriever_factory):
        repo = StubRepo([])
        response = await retriever_factory(repo).search(make_request("How much does it cost?"))
        assert response.requires_live_data[0].reason


class TestPolicyMetadata:
    async def test_document_policy_attached_when_scoped(self, retriever_factory):
        repo = StubRepo(
            [hit("yv-eye-001", "usage", "Apply once daily.")],
            document={
                "canonical_product_id": "yv-eye-001",
                "product_name": "Fernwing Volume Mascara",
                "answer_policy": {"medical_diagnosis_or_treatment": "redirect"},
                "citation_required_topics": ["ingredient efficacy"],
                "medical_escalation_topics": ["eye injury"],
            },
        )
        response = await retriever_factory(repo).search(make_request("How do I use it?", product_id="yv-eye-001"))
        assert response.answer_policy == {"medical_diagnosis_or_treatment": "redirect"}
        assert response.citation_required_topics == ["ingredient efficacy"]
        assert response.medical_escalation_topics == ["eye injury"]

    async def test_no_policy_when_unscoped(self, retriever_factory):
        repo = StubRepo([hit("yv-eye-001", "benefits", "Volume.")])
        response = await retriever_factory(repo).search(make_request("What adds lash volume?"))
        assert response.answer_policy is None
