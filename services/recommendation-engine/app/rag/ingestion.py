"""Catalogue ingestion pipeline.

Load Product.json -> validate -> build documents/aliases/semantic chunks ->
hash -> skip unchanged (no embedding call) -> batch-embed changed content ->
upsert documents, aliases and chunks -> delete chunks that disappeared ->
record the run. Re-running against an unchanged catalogue performs zero
embedding calls and inserts no duplicate rows.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.rag.chunker import SemanticChunk, build_chunks, build_document, build_source_version, extract_aliases
from app.rag.providers import EmbeddingProvider, EmbeddingProviderError
from app.rag.production import contains_prompt_injection
from app.rag.normalizer import stable_chunk_id
from app.rag.repository import ChunkUpsert, RagRepository
from app.rag.config import EmbeddingSpaceMismatchError, RagSettings

logger = logging.getLogger(__name__)


class CatalogueValidationError(ValueError):
    """The catalogue file does not meet the minimal ingestion contract."""


def load_brand_knowledge(path: Path) -> dict[str, Any]:
    """Convert the owner-approved brand source into the common RAG contract."""
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogueValidationError(f"brand knowledge file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise CatalogueValidationError(f"brand knowledge is not valid JSON: {path}: {error}") from error
    if not isinstance(source, dict) or not source.get("document_id") or not source.get("policy_title"):
        raise CatalogueValidationError("brand knowledge must contain document_id and policy_title")

    policies = source.get("public_policy") or {}
    policy_questions = {
        "cruelty_free": "Are YAFA VANAM products cruelty-free and certified?",
        "vegan": "Are all YAFA VANAM products vegan?",
        "charitable_giving": "Does YAFA VANAM donate sales revenue to charity?",
    }
    customer_questions: list[dict[str, str]] = []
    for key, question in policy_questions.items():
        item = policies.get(key) or {}
        answer = " ".join(
            value.strip()
            for value in (str(item.get("approved_answer") or ""), str(item.get("star_note") or ""))
            if value.strip()
        )
        if answer:
            customer_questions.append({"question": question, "answer": answer})
    for entry in source.get("conversational_inputs") or []:
        if not isinstance(entry, dict):
            continue
        examples = [str(value).strip() for value in entry.get("example_inputs") or [] if str(value).strip()]
        guidance = str(entry.get("response_guidance") or "").strip()
        if examples and guidance:
            customer_questions.append({
                "question": " / ".join(examples[:4]),
                "answer": guidance,
            })

    aliases = [
        "YAFA VANAM policy", "YAFA VANAM values", "cruelty-free", "vegan policy",
        "charity policy", "animal testing", "one percent giving",
    ]
    return {
        "id": str(source["document_id"]),
        "name": str(source["policy_title"]),
        "brand": str(source.get("brand") or "YAFA VANAM"),
        "category": "Brand Knowledge",
        "subcategory": "Policies and Conversation",
        "product_type": "Brand Knowledge Source",
        "status": str(source.get("status") or "approved"),
        "description": {
            "full": "Owner-approved YAFA VANAM brand values, claim definitions, conversational guidance, and safety boundaries."
        },
        "metadata": {"data_version": str(source.get("version") or "unknown")},
        "rag": {
            "enabled": True,
            "source_version": str(source.get("version") or "unknown"),
            "search_aliases": aliases,
            "topics": aliases,
            "customer_questions": customer_questions,
            "answer_policy": source.get("assistant_answer_rules") or {},
            "medical_escalation_topics": [
                "severe reaction", "persistent irritation", "eye injury",
                "suspected allergy", "pregnancy-related ingredient question",
            ],
        },
        "_rag_source_file": path.name,
    }


@dataclass
class IngestionStats:
    products_seen: int = 0
    documents_upserted: int = 0
    chunks_seen: int = 0
    chunks_new_or_changed: int = 0
    embeddings_generated: int = 0
    chunks_skipped_unchanged: int = 0
    chunks_deleted: int = 0
    documents_revoked: int = 0
    stopped_reason: str | None = None
    products_without_chunks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "products_seen": self.products_seen,
            "documents_upserted": self.documents_upserted,
            "chunks_seen": self.chunks_seen,
            "chunks_new_or_changed": self.chunks_new_or_changed,
            "embeddings_generated": self.embeddings_generated,
            "chunks_skipped_unchanged": self.chunks_skipped_unchanged,
            "chunks_deleted": self.chunks_deleted,
            "documents_revoked": self.documents_revoked,
        }
        if self.stopped_reason:
            payload["stopped_reason"] = self.stopped_reason
        return payload


def load_catalogue(path: Path, product_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Read and validate the canonical catalogue file.

    The whole file is always validated first; ``product_ids`` then narrows the
    returned list (single-product trials like Soft Ember-first ingestion).
    Unknown ids are an error so typos never look like successful runs.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogueValidationError(f"catalogue file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise CatalogueValidationError(f"catalogue file is not valid JSON: {path}: {error}") from error

    if not isinstance(raw, list) or not raw:
        raise CatalogueValidationError("catalogue must be a non-empty JSON array of products")

    problems: list[str] = []
    seen_ids: set[str] = set()
    for index, product in enumerate(raw):
        if not isinstance(product, dict):
            problems.append(f"[{index}] record is not an object")
            continue
        product_id = str(product.get("id") or "").strip()
        name = str(product.get("name") or "").strip()
        if not product_id:
            problems.append(f"[{index}] missing 'id'")
        elif product_id in seen_ids:
            problems.append(f"[{index}] duplicate product id {product_id!r}")
        else:
            seen_ids.add(product_id)
        if not name:
            problems.append(f"{product_id or index}: missing 'name'")
        if not product.get("rag"):
            problems.append(f"{product_id or index}: missing 'rag' section")
    if problems:
        raise CatalogueValidationError(
            f"catalogue validation failed with {len(problems)} problem(s): " + "; ".join(problems[:10])
        )

    if product_ids is not None:
        wanted = [pid.strip() for pid in product_ids if pid.strip()]
        missing = sorted(set(wanted) - seen_ids)
        if missing:
            raise CatalogueValidationError(
                f"requested product id(s) not in catalogue: {', '.join(missing)}"
            )
        return [product for product in raw if str(product.get("id")) in set(wanted)]
    return raw


def chunk_identity(chunk: SemanticChunk, source_version: str, tenant_id: str = "public") -> str:
    """Stable row identity per spec: product_id + chunk_type (+local key) +
    source_version + normalized content hash."""
    type_key = chunk.chunk_type if not chunk.local_key else f"{chunk.chunk_type}#{chunk.local_key}"
    identity_product = chunk.canonical_product_id if tenant_id == "public" else f"{tenant_id}:{chunk.canonical_product_id}"
    return stable_chunk_id(identity_product, type_key, source_version, chunk.source_hash)


async def ingest_catalogue(
    repo: RagRepository,
    provider: EmbeddingProvider,
    settings: RagSettings,
    *,
    force_embed: bool = False,
    product_ids: list[str] | None = None,
    log: Callable[[str], None] | None = None,
) -> IngestionStats:
    """Ingest (or refresh) the catalogue. Idempotent and resumable.

    Await from the caller's event loop (scripts use asyncio.run). The repository
    stays synchronous on purpose: psycopg calls are local and fast, while the
    embedding provider is genuinely I/O-bound.

    Resumability: provider failures (free-tier rate limits, outages) stop the
    run safely after the products completed so far. Committed products are
    never duplicated — re-running skips unchanged chunks and continues the
    remaining work.

    Embedding-space guard: stored embeddings from a different provider/model/
    dimension are refused unless force_embed is set (the rebuild script pairs
    force_embed with clearing all vectors first).
    """
    emit = log or (lambda message: logger.info(message))
    catalogue_path = settings.catalogue_path
    source_file = catalogue_path.name
    products = load_catalogue(catalogue_path, product_ids)
    if product_ids is None and settings.brand_knowledge_path is not None:
        products.append(load_brand_knowledge(settings.brand_knowledge_path))

    repo.ensure_schema(provider.dimension)

    stored = repo.get_embedding_metadata()
    if stored is not None and not force_embed:
        current = (provider.provider_name, provider.model_name, provider.dimension)
        previous = (
            stored["embedding_provider"],
            stored["embedding_model"],
            stored["embedding_dimension"],
        )
        if current != previous:
            raise EmbeddingSpaceMismatchError(
                f"stored embeddings were produced by {previous} but this run would use {current}; "
                "run scripts/rebuild_embeddings.py to rebuild the embedding space"
            )

    run_id = repo.start_run(source_file, _catalogue_version(products))
    stats = IngestionStats()
    products_by_tenant: dict[str, set[str]] = {}
    source_files_by_tenant: dict[str, set[str]] = {}

    try:
        stopped = False
        for product in products:
            stats.products_seen += 1
            document = build_document(product, str(product.get("_rag_source_file") or source_file))
            tenant_id = str(product.get("_rag_tenant_id") or "public")
            document["tenant_id"] = tenant_id
            products_by_tenant.setdefault(tenant_id, set()).add(document["canonical_product_id"])
            source_files_by_tenant.setdefault(tenant_id, set()).add(document["source_file"])
            version = document["source_version"]
            rag_enabled = bool((product.get("rag") or {}).get("enabled", True))
            chunks = build_chunks(product) if rag_enabled else []
            unsafe_chunks = [chunk for chunk in chunks if contains_prompt_injection(chunk.content, chunk.metadata)]
            if unsafe_chunks:
                emit(
                    f"quarantined {len(unsafe_chunks)} instruction-like chunk(s) for "
                    f"{document['canonical_product_id']}"
                )
                chunks = [chunk for chunk in chunks if chunk not in unsafe_chunks]
            if not chunks:
                stats.products_without_chunks.append(document["canonical_product_id"])
            aliases = extract_aliases(product)

            document_id = repo.upsert_document(document)
            stats.documents_upserted += 1
            repo.replace_aliases(document["canonical_product_id"], aliases, tenant_id=tenant_id)

            existing = repo.existing_chunk_hashes(document["canonical_product_id"], tenant_id=tenant_id)
            pending: list[tuple[str, SemanticChunk]] = []
            for chunk in chunks:
                stats.chunks_seen += 1
                chunk_id = chunk_identity(chunk, version, tenant_id)
                prior = existing.get(chunk_id)
                if prior is not None and not force_embed and prior[1] == chunk.source_hash:
                    stats.chunks_skipped_unchanged += 1
                    continue
                pending.append((chunk_id, chunk))

            vectors: dict[str, list[float]] = {}
            if pending:
                contents = [chunk.content for _, chunk in pending]
                try:
                    embedded = await provider.embed_documents(contents)
                except EmbeddingProviderError as error:
                    # Stop safely: finished products stay committed, this product's
                    # unchanged chunks remain valid, and the next run resumes here.
                    stats.stopped_reason = f"{type(error).__name__}: {error}"
                    emit(f"ingestion stopped safely after {stats.products_seen - 1} products: {error}")
                    break
                vectors = {chunk_id: vector for (chunk_id, _), vector in zip(pending, embedded)}
                stats.embeddings_generated += len(vectors)
                stats.chunks_new_or_changed += len(vectors)

            keep_ids: set[str] = set()
            for chunk in chunks:
                chunk_id = chunk_identity(chunk, version, tenant_id)
                keep_ids.add(chunk_id)
                metadata = dict(chunk.metadata)
                metadata.setdefault("tenant_id", tenant_id)
                metadata.setdefault(
                    "claim_key",
                    f"{chunk.canonical_product_id}:{chunk.chunk_type}:{chunk.local_key or 'primary'}",
                )
                repo.upsert_chunk(
                    ChunkUpsert(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        canonical_product_id=chunk.canonical_product_id,
                        chunk_type=chunk.chunk_type,
                        content=chunk.content,
                        trust_level=chunk.trust_level.value,
                        customer_factual_eligible=chunk.customer_factual_eligible,
                        requires_qualification=chunk.requires_qualification,
                        metadata=metadata,
                        source_hash=chunk.source_hash,
                        embedding=vectors.get(chunk_id),
                        tenant_id=tenant_id,
                    )
                )
            stats.chunks_deleted += repo.delete_missing_chunks(document["canonical_product_id"], keep_ids, tenant_id=tenant_id)
            if stats.products_seen % 20 == 0:
                emit(f"ingested {stats.products_seen}/{len(products)} products...")

        if stats.stopped_reason is None:
            # A full snapshot is authoritative: products removed entirely from
            # a source are revoked, not left retrievable forever. A targeted
            # product ingestion intentionally skips this global reconciliation.
            if product_ids is None:
                for tenant_id, keep_ids in products_by_tenant.items():
                    stats.documents_revoked += repo.revoke_missing_documents(
                        tenant_id=tenant_id,
                        source_files=source_files_by_tenant[tenant_id],
                        keep_product_ids=keep_ids,
                    )
            # Invalidate every service replica's cache through the shared
            # database revision, even when content hashes were unchanged.
            for tenant_id in products_by_tenant:
                repo.bump_corpus_revision(tenant_id)
            emit(
                f"ingestion complete: {stats.documents_upserted} documents, "
                f"{stats.chunks_new_or_changed} chunks embedded, "
                f"{stats.chunks_skipped_unchanged} skipped unchanged"
            )
            # Metadata is only stamped for a complete, consistent space.
            repo.set_embedding_metadata(
                provider=provider.provider_name,
                model=provider.model_name,
                dimension=provider.dimension,
            )
    finally:
        notes = f"force_embed={force_embed}"
        if stats.stopped_reason:
            notes += f"; stopped: {stats.stopped_reason}"
        repo.finish_run(run_id, stats.as_dict(), notes=notes)
    return stats


def _catalogue_version(products: list[dict[str, Any]]) -> str:
    versions = sorted({build_source_version(product) for product in products})
    return "+".join(versions)[:200]
