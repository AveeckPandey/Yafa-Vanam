-- Monotonic corpus revision used for cross-process cache invalidation.
CREATE TABLE IF NOT EXISTS rag_corpus_revisions (
    tenant_id TEXT PRIMARY KEY,
    revision BIGINT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO rag_corpus_revisions (tenant_id, revision)
VALUES ('public', 1)
ON CONFLICT (tenant_id) DO NOTHING;
