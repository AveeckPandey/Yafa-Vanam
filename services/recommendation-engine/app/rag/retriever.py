"""Retrieval orchestration: resolve -> scope -> search -> enforce -> rerank.

Pipeline per spec:
    query -> live-data intent detection
          -> product/alias resolution (exact before vector search)
          -> metadata filter (PDP page-context product scope)
          -> vector retrieval (explicit chunk_type/trust_level filters)
          -> centralized claim-safety re-check
          -> deterministic rerank (only when RAG_RERANK_ENABLED; off in Phase 1)

No LLM generation happens here: the response returns raw retrieved chunks so
the Yafa orchestrator (later phase) can decide presentation.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time

from app.rag.config import RagSettings
from app.rag.cache import AsyncTTLCache
from app.rag.providers import EmbeddingProvider, EmbeddingProviderError
from app.rag.filters import _STOPWORDS as _QUERY_STOPWORDS
from app.rag.filters import detect_live_data_domains, is_pure_live_data_query
from app.rag.models import LiveDataDomain, TrustLevel
from app.rag.normalizer import normalize_alias
from app.rag.repository import RagRepository, SearchHit
from app.rag.reranker import rerank
from app.rag.production import select_safe_evidence
from app.rag.telemetry import RetrievalTrace
from app.rag.schemas import (
    LiveRequirement,
    RagSearchRequest,
    RagSearchResponse,
    RetrievedChunk,
)
from app.rag.source_policy import can_surface_as_customer_fact

_LIVE_DOMAIN_REASONS = {
    LiveDataDomain.INVENTORY: "stock levels live in the commerce backend",
    LiveDataDomain.AVAILABILITY: "purchase availability is decided by the commerce backend",
    LiveDataDomain.PRICE: "current price lives in the commerce backend",
    LiveDataDomain.DISCOUNTS: "promotions and discounts are managed by the commerce backend",
    LiveDataDomain.REVIEWS: "customer reviews are stored by the commerce backend",
    LiveDataDomain.RATINGS: "product ratings are computed from live review data",
    LiveDataDomain.CART: "cart contents belong to the commerce backend session",
    LiveDataDomain.ORDER_STATUS: "order status comes from the commerce backend",
    LiveDataDomain.SHIPPING: "shipping estimates come from the commerce backend",
}

# Vector-search candidate pool size before reranking/diversity capping.
_POOL_MULTIPLIER = 4


class RetrievalUnavailableError(EmbeddingProviderError):
    """The vector store is unhealthy; callers must use the safe fallback."""

# A free embedding endpoint can briefly rate-limit. These intentionally small
# expansions keep common fragrance language useful during that outage without
# turning the fallback into an unbounded recommendation or live-data search.
_KEYWORD_STOPWORDS = _QUERY_STOPWORDS | frozenset({
    "product", "products", "yafa", "vanam", "fragrance", "fragrances",
    "scent", "scents", "smell", "smells", "perfume", "perfumes",
})
_KEYWORD_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "aqua": ("aquatic", "watery", "marine"),
    "aquatic": ("aqua", "watery", "marine"),
}
_KEYWORD_TOKEN = re.compile(r"[a-z0-9]+")


def _scope_from_request(request: RagSearchRequest) -> tuple[str | None, str]:
    """(product_id, resolution) implied by an explicit id or PDP page context."""
    if request.product_id:
        return request.product_id, "explicit_product_id"
    context = request.page_context
    if context and context.type == "product" and context.product_id:
        # "What does this smell like?" on a PDP means that product only.
        return context.product_id, "page_context"
    return None, "none"


class RagRetriever:
    def __init__(self, repo: RagRepository, provider: EmbeddingProvider, settings: RagSettings | None = None) -> None:
        self._repo = repo
        self._provider = provider
        self._settings = settings or RagSettings.from_env()
        self._cache = AsyncTTLCache(
            ttl_seconds=self._settings.cache_ttl_seconds,
            max_entries=self._settings.cache_max_entries,
        )
        self._embedding_semaphore = asyncio.Semaphore(self._settings.max_concurrent_embeddings)
        self._repository_failures = 0
        self._repository_open_until = 0.0
        self._known_revisions: dict[str, int] = {}

    async def search(self, request: RagSearchRequest) -> RagSearchResponse:
        """Search verified knowledge with cache coalescing and a Bedrock budget.

        The cache key intentionally excludes user and conversation state; this
        endpoint returns only catalogue facts. Identical concurrent requests
        share one Bedrock embedding call, which prevents a cache stampede when
        traffic spikes.
        """
        revision = self._known_revisions.get(request.tenant_id, 1)
        if time.monotonic() < self._repository_open_until:
            cached = await self._cache.get(self._cache_key(request, revision))
            if cached is not None:
                return cached
            raise RetrievalUnavailableError("knowledge store is temporarily unavailable")
        if hasattr(self._repo, "get_corpus_revision"):
            try:
                current_revision = self._repo.get_corpus_revision(request.tenant_id)
            except Exception as exc:
                self._record_repository_failure()
                cached = await self._cache.get(self._cache_key(request, revision))
                if cached is not None:
                    return cached
                raise RetrievalUnavailableError("knowledge store is temporarily unavailable") from exc
            if current_revision != revision:
                await self._cache.invalidate_all()
                revision = current_revision
                self._known_revisions[request.tenant_id] = revision

        key = self._cache_key(request, revision)
        try:
            response = await self._cache.get_or_load(key, lambda: self._search_uncached(request))
        except EmbeddingProviderError:
            raise
        except Exception as exc:
            self._record_repository_failure()
            raise RetrievalUnavailableError("knowledge store is temporarily unavailable") from exc
        self._repository_failures = 0
        self._repository_open_until = 0.0
        return response

    def _record_repository_failure(self) -> None:
        self._repository_failures += 1
        if self._repository_failures >= self._settings.circuit_breaker_failures:
            self._repository_open_until = time.monotonic() + self._settings.circuit_breaker_reset_seconds

    def _cache_key(self, request: RagSearchRequest, corpus_revision: int = 1) -> str:
        context = request.page_context
        payload = {
            "namespace": self._settings.cache_namespace,
            "corpus_revision": corpus_revision,
            "query": request.query.strip().lower(),
            "product_id": request.product_id,
            "page_product_id": context.product_id if context else None,
            "page_type": context.type if context else None,
            "top_k": request.top_k,
            "customer": request.allowed_for_customer,
            "chunk_types": sorted(request.chunk_types or []),
            "trust_levels": sorted(level.value for level in request.trust_levels or []),
            "tenant_id": request.tenant_id,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def _embed_query(self, query: str) -> list[float]:
        """Bound inbound embedding concurrency and fail quickly under load."""
        try:
            async with self._embedding_semaphore:
                return await asyncio.wait_for(
                    self._provider.embed_query(query), timeout=self._settings.query_timeout_seconds
                )
        except TimeoutError as exc:
            raise EmbeddingProviderError("embedding request timed out") from exc

    async def _search_uncached(self, request: RagSearchRequest) -> RagSearchResponse:
        query = request.query.strip()
        trace = RetrievalTrace(request_id=request.request_id, query=query, tenant_id=request.tenant_id)
        live_domains = detect_live_data_domains(query)
        # Pure live questions ("Is this in stock?") must never be answered from
        # static JSON: retrieval results stay empty and the orchestrator asks
        # the Go commerce backend instead.
        pure_live_question = is_pure_live_data_query(query)

        scope_id, scope_resolution = _scope_from_request(request)

        resolved_id: str | None = None
        alias_rank = 0
        ambiguous_candidates: list[dict[str, str]] = []
        if scope_id is None:
            resolved_id, alias_rank, ambiguous_candidates = self._resolve_by_alias(query, request.tenant_id)
        effective_scope = scope_id or resolved_id
        if scope_id:
            resolution = scope_resolution
        elif resolved_id:
            resolution = "exact_alias" if alias_rank >= 3 else "normalized_alias"
        elif ambiguous_candidates:
            resolution = "ambiguous_alias"
        else:
            resolution = "none"

        results: list[RetrievedChunk] = []
        if not pure_live_question:
            trust_levels = [level.value for level in request.trust_levels] if request.trust_levels else None
            try:
                query_vector = await self._embed_query(query)
            except EmbeddingProviderError:
                # A provider outage must not make an already-resolved product
                # fact disappear. Generic product-fact searches can also use
                # a deterministic, bounded term match over the same verified
                # fact type. It never exposes live data or recommendations.
                if not request.chunk_types:
                    raise
                if effective_scope:
                    hits = self._repo.fetch_verified_chunks(
                        product_id=effective_scope,
                        customer_factual_only=request.allowed_for_customer,
                        top_k=min(request.top_k * _POOL_MULTIPLIER, 40),
                        chunk_types=request.chunk_types,
                        trust_levels=trust_levels,
                        tenant_id=request.tenant_id,
                    )
                else:
                    hits = self._keyword_fallback(
                        query,
                    request,
                    trust_levels=trust_levels,
                    tenant_id=request.tenant_id,
                    )
                    if not hits:
                        raise
            else:
                hits = self._repo.search(
                    query_vector,
                    product_ids=[effective_scope] if effective_scope else None,
                    customer_factual_only=request.allowed_for_customer,
                    top_k=min(request.top_k * _POOL_MULTIPLIER, 40),
                    chunk_types=request.chunk_types,
                    trust_levels=trust_levels,
                    tenant_id=request.tenant_id,
                )
            pool = self._policy_filter(hits, request.allowed_for_customer)
            pool = [
                hit for hit in pool
                if hit.similarity == 0.0 or hit.similarity >= self._settings.min_grounding_similarity
            ]
            selected = select_safe_evidence(
                pool, tenant_id=request.tenant_id, max_items=min(request.top_k * _POOL_MULTIPLIER, 40)
            )
            trace.record(
                "retrieval",
                candidates=len(hits),
                policy_eligible=len(pool),
                injection_rejected=selected.rejected_injection,
                conflicts=selected.conflicts,
                chunk_ids=[str(hit.chunk_id) for hit in selected.hits[:8]],
                scores=[round(hit.similarity, 4) for hit in selected.hits[:8]],
            )
            if self._settings.rerank_enabled:
                results = [self._to_chunk(hit) for hit in rerank(selected.hits, query, request.top_k)]
            else:
                # Phase 1 default: vector similarity order, or the explicit
                # known-product fallback order when embeddings are unavailable.
                results = [self._to_chunk(hit) for hit in selected.hits[: request.top_k]]
        else:
            selected = select_safe_evidence([], tenant_id=request.tenant_id, max_items=request.top_k)

        document = self._repo.document_for_product(effective_scope, tenant_id=request.tenant_id) if effective_scope else None
        response = RagSearchResponse(
            request_id=request.request_id,
            query=query,
            product_id=effective_scope,
            resolved_product_id=resolved_id,
            resolution=resolution,
            results=results,
            requires_live_data=[
                LiveRequirement(domain=domain, reason=_LIVE_DOMAIN_REASONS[domain]) for domain in live_domains
            ],
            answer_policy=(document or {}).get("answer_policy") or None,
            citation_required_topics=(document or {}).get("citation_required_topics") or [],
            medical_escalation_topics=(document or {}).get("medical_escalation_topics") or [],
            conflicts=selected.conflicts,
        )
        trace.record("response", result_count=len(results), live_domains=[item.domain.value for item in response.requires_live_data])
        trace.emit(outcome="ok")
        return response

    # -- helpers ---------------------------------------------------------------

    def _resolve_by_alias(self, query: str, tenant_id: str = "public") -> tuple[str | None, int, list[dict[str, str]]]:
        """Exact/normalized alias match before any vector work.

        Returns (resolved_product_id | None, best_rank, ambiguous_candidates).
        Only matches at the strongest evidence level compete: a product whose
        name fully appears ("Soft Ember Warm Fragrance Concept") outranks one
        merely prefix-matched, and a unique survivor pins retrieval to it
        ("Soft Ember" -> yv-frag-010). Several equally strong products sharing
        the alias ("mascara") stays catalogue-wide.
        """
        normalized = normalize_alias(query)
        if len(normalized) < 3:
            # Very short fragments are not reliable product identifiers.
            return None, 0, []
        matches = self._repo.resolve_aliases(normalized, tenant_id=tenant_id)
        if not matches:
            return None, 0, []
        # A full product name must beat a shorter collection alias at the
        # same evidence level ("Forest Rain Body Mist" over "Forest Rain").
        # Otherwise an exact customer question becomes needlessly ambiguous
        # and cannot use either vector retrieval or the outage fallback.
        best_evidence = max((match.match_rank, match.matched_alias_length) for match in matches)
        strongest = [
            match
            for match in matches
            if (match.match_rank, match.matched_alias_length) == best_evidence
        ]
        product_ids = {match.canonical_product_id for match in strongest}
        if len(product_ids) == 1:
            return next(iter(product_ids)), best_evidence[0], []
        candidates = [
            {"product_id": match.canonical_product_id, "product_name": match.product_name}
            for match in strongest
        ]
        return None, best_evidence[0], candidates[:10]

    @staticmethod
    def _policy_filter(hits: list[SearchHit], allowed_for_customer: bool) -> list[SearchHit]:
        """Centralized claim-safety gate, re-applied even after SQL pre-filtering.

        Internal mode (allowed_for_customer=False) keeps everything visible so
        developers can inspect what was withheld and why.
        """
        if not allowed_for_customer:
            return hits
        return [
            hit for hit in hits
            if hit.customer_factual_eligible and can_surface_as_customer_fact(hit.metadata)
        ]

    def _keyword_fallback(
        self,
        query: str,
        request: RagSearchRequest,
        *,
        trust_levels: list[str] | None,
        tenant_id: str,
    ) -> list[SearchHit]:
        """Rank a small verified fact pool when embeddings are temporarily down.

        This is deliberately narrower than normal global retrieval: it is only
        enabled for a caller-supplied factual chunk type, has to match a
        meaningful query term, and de-duplicates products before returning.
        """
        weights = self._keyword_weights(query)
        if not weights:
            return []
        candidates = self._repo.fetch_eligible_chunks(
            customer_factual_only=request.allowed_for_customer,
            top_k=min(request.top_k * _POOL_MULTIPLIER * 3, 120),
            chunk_types=request.chunk_types,
            trust_levels=trust_levels,
            tenant_id=tenant_id,
        )
        ranked: list[tuple[int, SearchHit]] = []
        for hit in candidates:
            haystack = f"{hit.product_name} {hit.content}".lower()
            score = sum(weight for term, weight in weights.items() if term in haystack)
            if score:
                ranked.append((score, hit))
        ranked.sort(key=lambda item: (-item[0], item[1].product_name, item[1].chunk_id))

        results: list[SearchHit] = []
        product_ids: set[str] = set()
        for _, hit in ranked:
            if hit.product_id in product_ids:
                continue
            product_ids.add(hit.product_id)
            results.append(hit)
            if len(results) == request.top_k:
                break
        return results

    @staticmethod
    def _keyword_weights(query: str) -> dict[str, int]:
        """Meaningful lexical terms, plus cautious scent-language aliases."""
        weights: dict[str, int] = {}
        for term in _KEYWORD_TOKEN.findall(query.lower()):
            if len(term) < 3 or term in _KEYWORD_STOPWORDS:
                continue
            weights[term] = max(weights.get(term, 0), 3)
            for synonym in _KEYWORD_EXPANSIONS.get(term, ()):
                weights[synonym] = max(weights.get(synonym, 0), 1)
        return weights

    def _to_chunk(self, hit: SearchHit) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=str(hit.chunk_id),
            product_id=hit.product_id,
            product_name=hit.product_name,
            chunk_type=hit.chunk_type,
            content=hit.content,
            similarity=round(hit.similarity, 4),
            trust_level=TrustLevel(hit.trust_level),
            customer_factual_eligible=hit.customer_factual_eligible,
            requires_qualification=hit.requires_qualification,
            metadata=hit.metadata or {},
        )


def build_retriever(settings: RagSettings | None = None) -> RagRetriever:
    """Wire a retriever from environment configuration."""
    from app.rag.providers import build_provider

    resolved = settings or RagSettings.from_env()
    if not resolved.vector_database_url:
        raise RuntimeError("VECTOR_DATABASE_URL is not configured; cannot build RAG retriever")
    repo = RagRepository(resolved.vector_database_url)
    provider = build_provider(resolved)
    return RagRetriever(repo, provider, resolved)


__all__ = ["RagRetriever", "build_retriever"]
