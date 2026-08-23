-- Embedding column, vector index and embedding-space metadata.
--
-- The dimension is fixed at 2048 for the locked Phase 1 provider
-- (nvidia/nemotron-3-embed-1b via OpenRouter). A different model dimension
-- requires a NEW migration and a full rebuild_embeddings run — never a silent
-- reuse of this column.
--
-- No ANN index here: pgvector HNSW/IVFFlat support at most 2000 dimensions,
-- so retrieval uses exact cosine scan. At catalogue scale (hundreds to low
-- thousands of chunks) exact scan is both fast and perfectly recalled. If
-- chunk counts ever grow into the hundreds of thousands, add a halfvec
-- expression index (pgvector >= 0.7):
--   CREATE INDEX ... ON rag_chunks
--       USING hnsw ((embedding::halfvec(2048)) halfvec_cosine_ops);
-- and cast identically in repository search SQL.

ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding VECTOR(2048);

-- Singleton row recording which embedding space rag_chunks currently holds.
-- Ingestion refuses to run against a different provider/model/dimension
-- without an explicit rebuild.
CREATE TABLE IF NOT EXISTS rag_embedding_metadata (
    same_row BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (same_row),
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
