"""pgvector-backed storage for RAG documents, chunks and aliases.

Embeddings cross the wire as text cast to ::vector so no extra client library
beyond psycopg is required. All schema DDL is centralized here; the vector
column dimension is created from configuration and validated on every connect.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.rag.config import DimensionMismatchError
from app.rag.filters import _STOPWORDS as _QUERY_STOPWORDS


@dataclass(frozen=True)
class ChunkUpsert:
    chunk_id: str
    document_id: str
    canonical_product_id: str
    chunk_type: str
    content: str
    trust_level: str
    customer_factual_eligible: bool
    requires_qualification: bool
    metadata: dict[str, Any]
    source_hash: str
    embedding: list[float]


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    product_id: str
    product_name: str
    category: str | None
    subcategory: str | None
    product_type: str | None
    chunk_type: str
    content: str
    similarity: float
    trust_level: str
    customer_factual_eligible: bool
    requires_qualification: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class AliasMatch:
    """One candidate product from alias resolution."""

    canonical_product_id: str
    product_name: str
    match_rank: int  # 3 = exact equality, 2 = whole-phrase occurrence in query, 1 = alias extends query
    matched_alias_length: int


def _alias_match_rank(query: str, alias: str, *, specific: bool) -> int:
    """3 = exact equality, 2 = alias occurs as a whole phrase anywhere in the
    query, 1 = the alias extends a whole-word run of the query (partial name:
    "scent profile of soft ember" -> "soft ember warm fragrance concept";
    "fernwing" -> "fernwing volume mascara"). 0 = no trustworthy match
    ("ember" inside "december" must not count).

    Containment/partial branches need a *specific* name — an exact product
    name or a multi-word alias. Single generic words ("mascara", "fragrance")
    keep the legacy equality/prefix-only behaviour so their appearance
    mid-sentence cannot make every product look ambiguous.
    """
    if alias == query:
        return 3
    if not specific:
        return 0
    if re.search(rf"\b{re.escape(alias)}\b", query):
        return 2
    words = query.split()
    # Multi-word runs of the query...
    runs = [" ".join(words[i:j]) for i in range(len(words)) for j in range(i + 2, len(words) + 1)]
    # ...plus distinctive single words (a lone "soft" must not pin anything).
    runs += [word for word in words if len(word) >= 5 and word not in _QUERY_STOPWORDS]
    if any(alias.startswith(run + " ") for run in runs):
        return 1
    return 0


def _alias_is_specific(alias: str, is_exact_name: bool) -> bool:
    """True when the alias identifies one product well enough to be searched
    mid-sentence: an exact product name, or any multi-word alias. Generic
    single words ("mascara", "fragrance") stay equality/prefix-only so their
    appearance anywhere cannot make every product look ambiguous."""
    return bool(is_exact_name) or len(alias.split()) >= 2


class RagRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._connection: psycopg.Connection | None = None

    # -- connection -------------------------------------------------------

    def connection(self) -> psycopg.Connection:
        if self._connection is None or self._connection.closed:
            self._connection = psycopg.connect(self._dsn, row_factory=dict_row)
            self._connection.autocommit = True
        return self._connection

    def close(self) -> None:
        if self._connection is not None and not self._connection.closed:
            self._connection.close()
        self._connection = None

    # -- schema -----------------------------------------------------------

    def ensure_schema(self, dimension: int) -> None:
        """Apply tracked SQL migrations, then verify the vector column dimension.

        Schema lives in services/recommendation-engine/migrations/*.sql (001
        base tables, 002 VECTOR(2048) + metadata). The configured dimension
        must match what the migrations created — a different embedding model
        needs a new migration plus an embeddings rebuild, never silent reuse.
        """
        if not isinstance(dimension, int) or dimension <= 0:
            raise ValueError(f"invalid embedding dimension: {dimension!r}")
        self.apply_migrations()
        self.validate_stored_dimension(dimension)

    def apply_migrations(self) -> list[str]:
        """Apply pending *.sql migrations in filename order.

        Each file runs once inside a transaction together with its tracking
        row; editing an applied file is refused so drift cannot hide.
        """
        migrations_dir = Path(__file__).resolve().parents[2] / "migrations"
        if not migrations_dir.is_dir():
            raise RuntimeError(f"migrations directory not found: {migrations_dir}")
        conn = self.connection()
        applied: list[str] = []
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_schema_migrations (
                    filename TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute("SELECT filename, checksum FROM rag_schema_migrations")
            known = {row["filename"]: row["checksum"] for row in cursor.fetchall()}
        for path in sorted(migrations_dir.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            record = known.get(path.name)
            if record is not None:
                if record != checksum:
                    raise RuntimeError(
                        f"migration {path.name} changed after being applied; add a new migration instead"
                    )
                continue
            with conn.transaction():
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    cursor.execute(
                        "INSERT INTO rag_schema_migrations (filename, checksum) VALUES (%s, %s)",
                        (path.name, checksum),
                    )
            applied.append(path.name)
        return applied

    def validate_stored_dimension(self, expected: int) -> None:
        stored = self.stored_dimension()
        if stored is not None and stored != expected:
            raise DimensionMismatchError(
                f"rag_chunks.embedding has dimension {stored} but the embedding model outputs {expected}; "
                "rebuild embeddings or reconfigure EMBEDDING_DIMENSION"
            )

    def stored_dimension(self) -> int | None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.atttypmod AS dimension
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'rag_chunks' AND a.attname = 'embedding'
                """
            )
            row = cursor.fetchone()
        if not row or not row["dimension"]:
            return None
        # pgvector stores the dimension directly in typmod; tolerate any packed
        # encoding (dim << 16 | varhdrsz) defensively.
        raw = row["dimension"]
        if raw < 65536:
            return raw
        return (raw - 4) // 65536

    # -- writes -----------------------------------------------------------

    # -- embedding-space metadata -----------------------------------------

    def get_embedding_metadata(self) -> dict[str, Any] | None:
        """Which provider/model/dimension produced the stored embeddings."""
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT embedding_provider, embedding_model, embedding_dimension
                FROM rag_embedding_metadata
                WHERE same_row
                """
            )
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "embedding_provider": row["embedding_provider"],
            "embedding_model": row["embedding_model"],
            "embedding_dimension": int(row["embedding_dimension"]),
        }

    def set_embedding_metadata(self, *, provider: str, model: str, dimension: int) -> None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rag_embedding_metadata
                    (same_row, embedding_provider, embedding_model, embedding_dimension, updated_at)
                VALUES (TRUE, %(provider)s, %(model)s, %(dimension)s, NOW())
                ON CONFLICT (same_row) DO UPDATE SET
                    embedding_provider = EXCLUDED.embedding_provider,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimension = EXCLUDED.embedding_dimension,
                    updated_at = NOW()
                """,
                {"provider": provider, "model": model, "dimension": dimension},
            )

    def clear_all_embeddings(self) -> int:
        """Null out every stored vector (rebuild safety: no mixed spaces mid-rebuild)."""
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE rag_chunks SET embedding = NULL")
            return cursor.rowcount

    # -- writes -----------------------------------------------------------

    def upsert_document(self, document: dict[str, Any]) -> str:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rag_documents (
                    id, canonical_product_id, product_name, category, subcategory, product_type,
                    source_file, source_version, data_version, answer_policy,
                    citation_required_topics, medical_escalation_topics, guardrails, updated_at
                )
                VALUES (
                    %(id)s, %(canonical_product_id)s, %(product_name)s, %(category)s, %(subcategory)s,
                    %(product_type)s, %(source_file)s, %(source_version)s, %(data_version)s,
                    %(answer_policy)s::jsonb, %(citation_required_topics)s::jsonb,
                    %(medical_escalation_topics)s::jsonb, %(guardrails)s::jsonb, NOW()
                )
                ON CONFLICT (canonical_product_id) DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    category = EXCLUDED.category,
                    subcategory = EXCLUDED.subcategory,
                    product_type = EXCLUDED.product_type,
                    source_file = EXCLUDED.source_file,
                    source_version = EXCLUDED.source_version,
                    data_version = EXCLUDED.data_version,
                    answer_policy = EXCLUDED.answer_policy,
                    citation_required_topics = EXCLUDED.citation_required_topics,
                    medical_escalation_topics = EXCLUDED.medical_escalation_topics,
                    guardrails = EXCLUDED.guardrails,
                    updated_at = NOW()
                RETURNING id
                """,
                {
                    **document,
                    "answer_policy": json.dumps(document.get("answer_policy") or {}),
                    "citation_required_topics": json.dumps(document.get("citation_required_topics") or []),
                    "medical_escalation_topics": json.dumps(document.get("medical_escalation_topics") or []),
                    "guardrails": json.dumps(document.get("guardrails") or {}),
                },
            )
            return cursor.fetchone()["id"]

    def replace_aliases(self, canonical_product_id: str, aliases: list[tuple[str, bool]]) -> None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM rag_product_aliases WHERE canonical_product_id = %s", (canonical_product_id,))
            cursor.executemany(
                """
                INSERT INTO rag_product_aliases (canonical_product_id, alias, normalized_alias, is_exact_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (canonical_product_id, normalized_alias) DO UPDATE
                    SET alias = EXCLUDED.alias, is_exact_name = EXCLUDED.is_exact_name
                """,
                [
                    (canonical_product_id, alias, normalized, is_exact)
                    for alias, normalized, is_exact in aliases
                ],
            )

    def existing_chunk_hashes(self, canonical_product_id: str) -> dict[str, tuple[str, str]]:
        """Return {chunk_id: (chunk_type, source_hash)} for skip-if-unchanged logic."""
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, chunk_type, source_hash FROM rag_chunks WHERE canonical_product_id = %s",
                (canonical_product_id,),
            )
            rows = cursor.fetchall()
        # psycopg returns UUID objects for the id column; identity comparisons
        # downstream use the string form produced by stable_chunk_id().
        return {str(row["id"]): (row["chunk_type"], row["source_hash"]) for row in rows}

    def delete_missing_chunks(self, canonical_product_id: str, keep_chunk_ids: set[str]) -> int:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM rag_chunks WHERE canonical_product_id = %s AND NOT (id = ANY(%s::uuid[]))",
                (
                    canonical_product_id,
                    list(keep_chunk_ids) or ["00000000-0000-0000-0000-000000000000"],
                ),
            )
            return cursor.rowcount

    def upsert_chunk(self, chunk: ChunkUpsert) -> None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO rag_chunks (
                    id, document_id, canonical_product_id, chunk_type, content, trust_level,
                    customer_factual_eligible, requires_qualification, metadata, embedding,
                    source_hash, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s, NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    trust_level = EXCLUDED.trust_level,
                    customer_factual_eligible = EXCLUDED.customer_factual_eligible,
                    requires_qualification = EXCLUDED.requires_qualification,
                    metadata = EXCLUDED.metadata,
                    -- NULL embedding means 'unchanged content': keep the stored vector.
                    embedding = COALESCE(EXCLUDED.embedding, rag_chunks.embedding),
                    source_hash = EXCLUDED.source_hash,
                    updated_at = NOW()
                """,
                (
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.canonical_product_id,
                    chunk.chunk_type,
                    chunk.content,
                    chunk.trust_level,
                    chunk.customer_factual_eligible,
                    chunk.requires_qualification,
                    json.dumps(chunk.metadata),
                    str(chunk.embedding) if chunk.embedding is not None else None,
                    chunk.source_hash,
                ),
            )

    def start_run(self, source_file: str, source_version: str) -> int:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO rag_ingestion_runs (source_file, source_version) VALUES (%s, %s) RETURNING id",
                (source_file, source_version),
            )
            return cursor.fetchone()["id"]

    def finish_run(self, run_id: int, stats: dict[str, Any], notes: str = "") -> None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE rag_ingestion_runs
                SET finished_at = NOW(), products_seen = %s, chunks_upserted = %s,
                    chunks_skipped = %s, embeddings_generated = %s, notes = %s
                WHERE id = %s
                """,
                (
                    stats.get("products_seen", 0), stats.get("chunks_upserted", 0),
                    stats.get("chunks_skipped", 0), stats.get("embeddings_generated", 0), notes, run_id,
                ),
            )

    # -- reads ------------------------------------------------------------

    def resolve_aliases(self, normalized_query: str) -> list[AliasMatch]:
        """Exact/normalized alias matches, best first. Empty means 'use vectors'.

        Matches the query against aliases in both directions AND inside it:
        "What is the scent profile of Soft Ember?" must pin yv-frag-010 even
        though only part of the name sits mid-sentence. The alias table is
        small (a few hundred rows), so candidate scanning happens in Python —
        word boundaries and partial-name runs are awkward to express as SQL
        LIKE patterns and product names may contain regex metacharacters.
        """
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.canonical_product_id, d.product_name,
                       a.normalized_alias, a.is_exact_name
                FROM rag_product_aliases a
                JOIN rag_documents d ON d.canonical_product_id = a.canonical_product_id
                """
            )
            rows = cursor.fetchall()

        best: dict[str, AliasMatch] = {}
        for row in rows:
            alias = row["normalized_alias"]
            rank = _alias_match_rank(
                normalized_query, alias,
                specific=_alias_is_specific(alias, bool(row["is_exact_name"])),
            )
            if rank == 0:
                continue
            candidate = AliasMatch(
                canonical_product_id=row["canonical_product_id"],
                product_name=row["product_name"],
                match_rank=rank,
                matched_alias_length=len(alias),
            )
            previous = best.get(candidate.canonical_product_id)
            if previous is None or (rank, candidate.matched_alias_length) > (
                previous.match_rank, previous.matched_alias_length
            ):
                best[candidate.canonical_product_id] = candidate
        return sorted(
            best.values(),
            key=lambda m: (-m.match_rank, -m.matched_alias_length, m.canonical_product_id),
        )

    def document_for_product(self, canonical_product_id: str) -> dict[str, Any] | None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT canonical_product_id, product_name, answer_policy,
                       citation_required_topics, medical_escalation_topics, guardrails
                FROM rag_documents WHERE canonical_product_id = %s
                """,
                (canonical_product_id,),
            )
            return cursor.fetchone()

    def all_chunk_content(self) -> list[tuple[str, str]]:
        """(chunk_id, content) for every stored chunk — used by rebuild_embeddings."""
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, content FROM rag_chunks ORDER BY id")
            return [(row["id"], row["content"]) for row in cursor.fetchall()]

    def store_embeddings(self, vectors: dict[str, list[float]]) -> None:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.executemany(
                "UPDATE rag_chunks SET embedding = %s::vector, updated_at = NOW() WHERE id = %s",
                [(str(vector), chunk_id) for chunk_id, vector in vectors.items()],
            )

    def search(
        self,
        query_vector: list[float],
        *,
        product_ids: list[str] | None = None,
        customer_factual_only: bool = True,
        top_k: int = 5,
        chunk_types: list[str] | None = None,
        trust_levels: list[str] | None = None,
    ) -> list[SearchHit]:
        conn = self.connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.canonical_product_id, d.product_name, d.category, d.subcategory,
                       d.product_type, c.chunk_type, c.content, c.trust_level,
                       c.customer_factual_eligible, c.requires_qualification, c.metadata,
                       1 - (c.embedding <=> %(query_vector)s::vector) AS similarity
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.embedding IS NOT NULL
                  AND (%(product_ids)s::text[] IS NULL OR c.canonical_product_id = ANY(%(product_ids)s::text[]))
                  AND (%(types)s::text[] IS NULL OR c.chunk_type = ANY(%(types)s::text[]))
                  AND (%(trusts)s::text[] IS NULL OR c.trust_level = ANY(%(trusts)s::text[]))
                  AND (%(customer_only)s = FALSE OR c.customer_factual_eligible)
                ORDER BY c.embedding <=> %(query_vector)s::vector
                LIMIT %(top_k)s
                """,
                {
                    "query_vector": str(query_vector),
                    "product_ids": product_ids,
                    "types": chunk_types,
                    "trusts": trust_levels,
                    "customer_only": customer_factual_only,
                    "top_k": top_k,
                },
            )
            rows = cursor.fetchall()
        return [
            SearchHit(
                chunk_id=row["id"],
                product_id=row["canonical_product_id"],
                product_name=row["product_name"],
                category=row["category"],
                subcategory=row["subcategory"],
                product_type=row["product_type"],
                chunk_type=row["chunk_type"],
                content=row["content"],
                similarity=float(row["similarity"]),
                trust_level=row["trust_level"],
                customer_factual_eligible=row["customer_factual_eligible"],
                requires_qualification=row["requires_qualification"],
                metadata=row["metadata"] or {},
            )
            for row in rows
        ]
