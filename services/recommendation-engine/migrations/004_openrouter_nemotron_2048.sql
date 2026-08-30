-- Restore the locked OpenRouter embedding space after the retired Titan V2
-- migration changed the vector column to 1024 dimensions. Chunks are derived
-- only from the checked-in product knowledge and are rebuilt immediately by
-- the ingestion job; documents and aliases remain intact.

TRUNCATE TABLE rag_chunks;
DELETE FROM rag_embedding_metadata;
ALTER TABLE rag_chunks
    ALTER COLUMN embedding TYPE VECTOR(2048)
    USING NULL::VECTOR(2048);
