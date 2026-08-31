-- Production retrieval index for the AWS Titan V2 embedding space.
--
-- The catalogue is small today, but HNSW keeps p95 query latency stable as
-- both traffic and approved knowledge grow. This normal index creation is
-- intentional: first deployment has a small corpus. For a later large corpus,
-- create a concurrently-built replacement in a dedicated maintenance release.

CREATE INDEX IF NOT EXISTS rag_chunks_embedding_hnsw_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
