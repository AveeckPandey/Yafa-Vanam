-- Switch the RAG store from the prior 2048-dimensional OpenRouter embedding
-- space to Liquid LFM2.5 Embedding 350M, which returns 1024 dimensions.
-- Chunks are fully derived from the checked-in product knowledge and must be
-- regenerated before retrieval resumes; documents and aliases remain intact.

TRUNCATE TABLE rag_chunks;
DELETE FROM rag_embedding_metadata;
ALTER TABLE rag_chunks
    ALTER COLUMN embedding TYPE VECTOR(1024)
    USING NULL::VECTOR(1024);
