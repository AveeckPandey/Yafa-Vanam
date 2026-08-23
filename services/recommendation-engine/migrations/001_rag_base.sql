-- RAG base schema: documents, chunks, aliases and ingestion-run audit.
-- Idempotent; applied once and tracked in rag_schema_migrations.
-- The embedding column itself is added by 002_rag_embeddings.sql.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY,
    canonical_product_id TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    product_type TEXT,
    source_file TEXT NOT NULL,
    source_version TEXT NOT NULL,
    data_version TEXT,
    answer_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    citation_required_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    medical_escalation_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    guardrails JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    canonical_product_id TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    content TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    customer_factual_eligible BOOLEAN NOT NULL DEFAULT TRUE,
    requires_qualification BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS rag_chunks_product_idx ON rag_chunks (canonical_product_id);

CREATE TABLE IF NOT EXISTS rag_product_aliases (
    id BIGSERIAL PRIMARY KEY,
    canonical_product_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    is_exact_name BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (canonical_product_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS rag_alias_lookup_idx ON rag_product_aliases (normalized_alias);

CREATE TABLE IF NOT EXISTS rag_ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    source_file TEXT,
    source_version TEXT,
    products_seen INTEGER NOT NULL DEFAULT 0,
    chunks_upserted INTEGER NOT NULL DEFAULT 0,
    chunks_skipped INTEGER NOT NULL DEFAULT 0,
    embeddings_generated INTEGER NOT NULL DEFAULT 0,
    notes TEXT
);
