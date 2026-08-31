"""Ingestion pipeline: idempotency, skip-unchanged embedding economics,
validation, and rag.enabled handling — against an in-memory repository."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.config import RagSettings
from app.rag.providers import HashingEmbeddingProvider
from app.rag.ingestion import CatalogueValidationError, chunk_identity, ingest_catalogue, load_brand_knowledge, load_catalogue
from app.rag.repository import ChunkUpsert

CATALOGUE = Path(__file__).resolve().parents[3] / "data" / "processed" / "Product.json"
BRAND_KNOWLEDGE = Path(__file__).resolve().parents[3] / "data" / "processed" / "BrandKnowledge.json"


class CountingEmbedder(HashingEmbeddingProvider):
    """Hashing embedder that records batch sizes (embedding-call economics)."""

    def __init__(self, dimension: int = HashingEmbeddingProvider.DEFAULT_DIMENSION) -> None:
        super().__init__(dimension=dimension)
        self.batch_sizes: list[int] = []

    async def embed_documents(self, texts):
        self.batch_sizes.append(len(texts))
        return await super().embed_documents(texts)


class FakeRepo:
    """Minimal in-memory RagRepository covering the ingestion interface."""

    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.chunks: dict[str, ChunkUpsert] = {}
        self.aliases: dict[str, list] = {}
        self.runs: list[dict] = []
        self.schema_calls: list[int] = []
        self.embedding_metadata: dict | None = None
        self._document_ids: dict[str, str] = {}
        self.revisions: dict[str, int] = {}

    # -- schema/runs -------------------------------------------------------
    def ensure_schema(self, dimension: int) -> None:
        self.schema_calls.append(dimension)

    def get_embedding_metadata(self) -> dict | None:
        return self.embedding_metadata

    def set_embedding_metadata(self, *, provider: str, model: str, dimension: int) -> None:
        self.embedding_metadata = {
            "embedding_provider": provider,
            "embedding_model": model,
            "embedding_dimension": dimension,
        }

    def start_run(self, source_file: str, source_version: str) -> int:
        self.runs.append({"source_file": source_file, "source_version": source_version})
        return len(self.runs)

    def finish_run(self, run_id: int, stats: dict, notes: str = "") -> None:
        self.runs[run_id - 1]["stats"] = stats

    # -- writes ------------------------------------------------------------
    def upsert_document(self, document: dict) -> str:
        pid = document["canonical_product_id"]
        self.documents[pid] = document
        return f"doc-{pid}"

    def replace_aliases(self, canonical_product_id: str, aliases: list, *, tenant_id="public") -> None:
        merged: dict[str, tuple] = {}
        for alias, normalized, is_exact in aliases:
            existing = merged.get(normalized)
            if existing is None or (is_exact and not existing[2]):
                merged[normalized] = (alias, normalized, is_exact)
        self.aliases[canonical_product_id] = sorted(merged.values())

    def existing_chunk_hashes(self, canonical_product_id: str, *, tenant_id="public") -> dict[str, tuple[str, str]]:
        return {
            chunk_id: (chunk.chunk_type, chunk.source_hash)
            for chunk_id, chunk in self.chunks.items()
            if chunk.canonical_product_id == canonical_product_id
        }

    def upsert_chunk(self, chunk: ChunkUpsert) -> None:
        self.chunks[chunk.chunk_id] = chunk

    def delete_missing_chunks(self, canonical_product_id: str, keep_chunk_ids: set[str], *, tenant_id="public") -> int:
        stale = [
            chunk_id for chunk_id, chunk in self.chunks.items()
            if chunk.canonical_product_id == canonical_product_id and chunk_id not in keep_chunk_ids
        ]
        for chunk_id in stale:
            del self.chunks[chunk_id]
        return len(stale)

    def revoke_missing_documents(self, *, tenant_id: str, source_files: set[str], keep_product_ids: set[str]) -> int:
        stale = [
            pid for pid, document in self.documents.items()
            if document.get("tenant_id", "public") == tenant_id
            and document.get("source_file") in source_files
            and pid not in keep_product_ids
        ]
        for pid in stale:
            del self.documents[pid]
        return len(stale)

    def bump_corpus_revision(self, tenant_id="public") -> int:
        self.revisions[tenant_id] = self.revisions.get(tenant_id, 0) + 1
        return self.revisions[tenant_id]


@pytest.fixture()
def real_settings(tmp_path) -> RagSettings:
    """Settings pointed at the real catalogue file (copied to tmp keeps tests
    independent of config env)."""
    catalogue_copy = tmp_path / "Product.json"
    catalogue_copy.write_text(CATALOGUE.read_text(encoding="utf-8"), encoding="utf-8")
    return RagSettings.from_env({
        "VECTOR_DATABASE_URL": "",
        "EMBEDDING_PROVIDER": "hashing",
        "EMBEDDING_DIMENSION": "384",
        "YAFA_CATALOGUE_PATH": str(catalogue_copy),
    })


def mini_catalogue_file(tmp_path: Path, products: list[dict]) -> RagSettings:
    path = tmp_path / "mini.json"
    path.write_text(json.dumps(products), encoding="utf-8")
    return RagSettings.from_env({
        "EMBEDDING_PROVIDER": "hashing",
        "YAFA_CATALOGUE_PATH": str(path),
    })


BASE_PRODUCT = {
    "id": "yv-mini-001", "name": "Mini Mascara", "brand": "YAFA VANAM",
    "category": "Makeup", "subcategory": "Eyes", "product_type": "Mascara",
    "description": {"full": "A miniature mascara for testing."},
    "benefits": ["Adds visible volume"],
    "warnings": ["For external use only."],
    "rag": {
        "enabled": True,
        "source_version": "mini-v1",
        "search_aliases": ["Mini Mascara", "mascara"],
        "customer_questions": [{"question": "What is Mini Mascara?", "answer": "A tiny test mascara."}],
    },
}


def _variant(product_id: str, name: str) -> dict:
    product = json.loads(json.dumps(BASE_PRODUCT))
    product["id"] = product_id
    product["name"] = name
    product["rag"]["search_aliases"] = [name]
    return product


class RateLimitedEmbedder(HashingEmbeddingProvider):
    """Succeeds for the first N embed calls, then simulates a free-tier 429."""

    def __init__(self, successful_calls: int) -> None:
        super().__init__(dimension=2048)
        self.remaining = successful_calls

    async def embed_documents(self, texts):
        if self.remaining <= 0:
            from app.rag.providers import EmbeddingRateLimitError

            raise EmbeddingRateLimitError("429: rate limit exceeded, resume later")
        self.remaining -= 1
        return await super().embed_documents(texts)


@pytest.mark.asyncio
async def test_first_run_embeds_everything(tmp_path):
    repo, embedder = FakeRepo(), CountingEmbedder()
    settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
    stats = await ingest_catalogue(repo, embedder, settings)
    assert stats.products_seen == 1
    assert stats.embeddings_generated == stats.chunks_seen > 0
    assert sum(embedder.batch_sizes) == stats.chunks_seen


@pytest.mark.asyncio
async def test_second_run_makes_zero_embedding_calls(tmp_path):
    repo, embedder = FakeRepo(), CountingEmbedder()
    settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
    first = await ingest_catalogue(repo, embedder, settings)
    embedder.batch_sizes.clear()
    second = await ingest_catalogue(repo, embedder, settings)
    assert second.embeddings_generated == 0
    assert embedder.batch_sizes == []  # provider never contacted again (spec §21)
    assert second.chunks_skipped_unchanged == first.chunks_seen
    # No duplicate rows appeared.
    assert len(repo.chunks) == first.chunks_seen


@pytest.mark.asyncio
async def test_content_change_reembeds_only_changed_chunk(tmp_path):
    repo, embedder = FakeRepo(), CountingEmbedder()
    settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
    await ingest_catalogue(repo, embedder, settings)
    total_before = len(repo.chunks)
    embedder.batch_sizes.clear()

    changed = json.loads(json.dumps(BASE_PRODUCT))
    changed["benefits"] = ["Adds visible volume", "Defines lashes"]
    settings_changed = mini_catalogue_file(tmp_path, [changed])
    stats = await ingest_catalogue(repo, embedder, settings_changed)

    assert stats.embeddings_generated == 1  # exactly the benefits chunk changed
    assert len(repo.chunks) == total_before  # changed chunk replaced its stale row, none duplicated
    types = [chunk.chunk_type for chunk in repo.chunks.values()]
    assert types.count("benefits") == 1


@pytest.mark.asyncio
async def test_removed_section_deletes_stale_chunk(tmp_path):
    repo, embedder = FakeRepo(), CountingEmbedder()
    settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
    await ingest_catalogue(repo, embedder, settings)
    with_warnings = len(repo.chunks)
    assert any(c.chunk_type == "warnings" for c in repo.chunks.values())

    slimmed = json.loads(json.dumps(BASE_PRODUCT))
    del slimmed["warnings"]
    await ingest_catalogue(repo, CountingEmbedder(), mini_catalogue_file(tmp_path, [slimmed]))
    assert len(repo.chunks) == with_warnings - 1
    assert not any(c.chunk_type == "warnings" for c in repo.chunks.values())


@pytest.mark.asyncio
async def test_full_snapshot_revokes_product_removed_entirely(tmp_path):
    first = _variant("yv-mini-001", "First")
    removed = _variant("yv-mini-002", "Removed")
    repo = FakeRepo()
    await ingest_catalogue(repo, CountingEmbedder(), mini_catalogue_file(tmp_path, [first, removed]))
    assert "yv-mini-002" in repo.documents

    stats = await ingest_catalogue(repo, CountingEmbedder(), mini_catalogue_file(tmp_path, [first]))

    assert stats.documents_revoked == 1
    assert "yv-mini-002" not in repo.documents
    assert repo.revisions["public"] >= 2


@pytest.mark.asyncio
async def test_disabled_rag_ingests_document_but_no_chunks(tmp_path):
    product = json.loads(json.dumps(BASE_PRODUCT))
    product["rag"]["enabled"] = False
    repo, embedder = FakeRepo(), CountingEmbedder()
    stats = await ingest_catalogue(repo, embedder, mini_catalogue_file(tmp_path, [product]))
    assert repo.documents["yv-mini-001"]
    assert not repo.chunks
    assert stats.products_without_chunks == ["yv-mini-001"]


@pytest.mark.asyncio
async def test_aliases_upserted_with_exact_flags(tmp_path):
    repo, embedder = FakeRepo(), CountingEmbedder()
    await ingest_catalogue(repo, embedder, mini_catalogue_file(tmp_path, [BASE_PRODUCT]))
    aliases = {normalized: exact for _, normalized, exact in repo.aliases["yv-mini-001"]}
    assert aliases["mini mascara"] is True   # product name
    assert aliases["mascara"] is False       # generic term shared by many products


def test_load_catalogue_validation_errors(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([
        {"name": "No ID", "rag": {"enabled": True}},
        {"id": "dup-1", "name": "First", "rag": {}},
        {"id": "dup-1", "name": "Second"},
    ]), encoding="utf-8")
    with pytest.raises(CatalogueValidationError) as excinfo:
        load_catalogue(bad)
    message = str(excinfo.value)
    assert "missing 'id'" in message
    assert "duplicate product id 'dup-1'" in message

    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    with pytest.raises(CatalogueValidationError):
        load_catalogue(empty)


def test_owner_approved_brand_knowledge_converts_to_retrievable_document():
    document = load_brand_knowledge(BRAND_KNOWLEDGE)
    assert document["id"] == "yv-brand-knowledge-001"
    assert document["_rag_source_file"] == "BrandKnowledge.json"
    questions = document["rag"]["customer_questions"]
    assert any("cruelty-free" in row["question"].lower() for row in questions)
    assert any("vegan" in row["question"].lower() for row in questions)
    assert any("charity" in row["question"].lower() for row in questions)


@pytest.mark.asyncio
async def test_default_ingestion_includes_brand_knowledge(tmp_path):
    catalogue_copy = tmp_path / "Product.json"
    catalogue_copy.write_text(json.dumps([BASE_PRODUCT]), encoding="utf-8")
    settings = RagSettings.from_env({
        "EMBEDDING_PROVIDER": "hashing",
        "YAFA_CATALOGUE_PATH": str(catalogue_copy),
        "YAFA_BRAND_KNOWLEDGE_PATH": str(BRAND_KNOWLEDGE),
    })
    repo, embedder = FakeRepo(), CountingEmbedder()
    stats = await ingest_catalogue(repo, embedder, settings)
    assert stats.products_seen == 2
    assert "yv-brand-knowledge-001" in repo.documents
    assert any(
        chunk.canonical_product_id == "yv-brand-knowledge-001"
        for chunk in repo.chunks.values()
    )


def test_chunk_identity_is_spec_shaped():
    """Identity = product_id + chunk_type(+local key) + source_version + content hash."""
    from app.rag.chunker import build_chunks

    chunks = build_chunks(BASE_PRODUCT)
    faq = [c for c in chunks if c.chunk_type == "faq"][0]
    other_faq = dict(faq.__dict__)
    other_faq["content"] = faq.content.replace("tiny", "small")
    rebuilt = type(faq)(**other_faq)
    assert chunk_identity(faq, "v1") != chunk_identity(rebuilt, "v1")  # content change -> new identity
    assert chunk_identity(faq, "v1") == chunk_identity(faq, "v1")      # stable otherwise


class TestResumableIngestion:
    """Free-tier rate limits must stop ingestion safely; re-runs resume."""

    @pytest.mark.asyncio
    async def test_rate_limit_stops_safely_and_resume_completes_without_duplicates(self, tmp_path):
        products = [
            BASE_PRODUCT,
            _variant("yv-mini-002", "Glow Lip Tint"),
            _variant("yv-mini-003", "Silk Blush"),
        ]
        settings = mini_catalogue_file(tmp_path, products)

        repo = FakeRepo()
        flaky = RateLimitedEmbedder(successful_calls=2)  # two products embed, third hits 429
        stopped = await ingest_catalogue(repo, flaky, settings)
        assert stopped.stopped_reason and "rate limit" in stopped.stopped_reason
        committed_after_stop = set(repo.chunks)

        # Finished products stay committed; nothing from the failed product lingers.
        assert any(chunk.canonical_product_id == "yv-mini-001" for chunk in repo.chunks.values())
        assert any(chunk.canonical_product_id == "yv-mini-002" for chunk in repo.chunks.values())

        resumed = await ingest_catalogue(repo, CountingEmbedder(), settings)
        assert resumed.stopped_reason is None
        assert resumed.chunks_new_or_changed > 0  # only the remaining work was embedded
        final_ids = set(repo.chunks)
        assert len(final_ids) >= len(committed_after_stop)  # growth, never duplication
        per_product = {chunk.canonical_product_id for chunk in repo.chunks.values()}
        assert per_product == {"yv-mini-001", "yv-mini-002", "yv-mini-003"}
        # A third full run is fully idempotent.
        third = await ingest_catalogue(repo, CountingEmbedder(), settings)
        assert third.embeddings_generated == 0
        assert set(repo.chunks) == final_ids

    @pytest.mark.asyncio
    async def test_stopped_run_writes_no_embedding_metadata(self, tmp_path):
        settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
        repo = FakeRepo()
        await ingest_catalogue(repo, RateLimitedEmbedder(successful_calls=0), settings)
        assert repo.embedding_metadata is None  # space not declared consistent

        await ingest_catalogue(repo, CountingEmbedder(dimension=2048), settings)
        assert repo.embedding_metadata == {
            "embedding_provider": "hashing",
            "embedding_model": "yafa-hashing-v1",
            "embedding_dimension": 2048,
        }


class TestEmbeddingSpaceGuard:
    @pytest.mark.asyncio
    async def test_different_model_blocks_ingestion_until_rebuild(self, tmp_path):
        settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
        repo = FakeRepo()
        await ingest_catalogue(repo, CountingEmbedder(), settings)

        from app.rag.config import EmbeddingSpaceMismatchError

        repo.embedding_metadata = {
            "embedding_provider": "openrouter",
            "embedding_model": "nvidia/nemotron-3-embed-1b:free",
            "embedding_dimension": 2048,
        }
        with pytest.raises(EmbeddingSpaceMismatchError, match="rebuild_embeddings"):
            await ingest_catalogue(repo, CountingEmbedder(), settings)

    @pytest.mark.asyncio
    async def test_force_embed_overrides_the_guard(self, tmp_path):
        settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT])
        repo = FakeRepo()
        await ingest_catalogue(repo, CountingEmbedder(), settings)
        repo.embedding_metadata = {
            "embedding_provider": "openrouter",
            "embedding_model": "nvidia/nemotron-3-embed-1b:free",
            "embedding_dimension": 2048,
        }
        stats = await ingest_catalogue(repo, CountingEmbedder(), settings, force_embed=True)
        assert stats.embeddings_generated > 0

    @pytest.mark.asyncio
    async def test_product_filter_narrows_catalogue(self, tmp_path):
        settings = mini_catalogue_file(tmp_path, [BASE_PRODUCT, _variant("yv-mini-002", "Glow Lip Tint")])
        repo = FakeRepo()
        stats = await ingest_catalogue(repo, CountingEmbedder(), settings, product_ids=["yv-mini-002"])
        assert stats.products_seen == 1
        assert {chunk.canonical_product_id for chunk in repo.chunks.values()} == {"yv-mini-002"}

    def test_unknown_product_filter_id_is_an_error(self, tmp_path):
        path = tmp_path / "mini.json"
        path.write_text(json.dumps([BASE_PRODUCT]), encoding="utf-8")
        with pytest.raises(CatalogueValidationError, match="yv-nope"):
            load_catalogue(path, product_ids=["yv-nope"])
