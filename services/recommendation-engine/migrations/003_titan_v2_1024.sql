-- Production embedding space: Amazon Titan Text Embeddings V2 at 1024 dims.
--
-- This migration intentionally clears old vectors/chunks before changing the
-- typmod. Content is rebuilt by the idempotent ingestion job in the new space;
-- mixing 2048- and 1024-dimensional embeddings would corrupt retrieval.

TRUNCATE TABLE rag_chunks;
DELETE FROM rag_embedding_metadata;
ALTER TABLE rag_chunks
    ALTER COLUMN embedding TYPE VECTOR(1024)
    USING NULL::VECTOR(1024);
