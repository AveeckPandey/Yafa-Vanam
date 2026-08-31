-- Enforce tenant isolation on every table that contains knowledge.
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS tenant_id TEXT;
UPDATE rag_chunks c
SET tenant_id = d.tenant_id
FROM rag_documents d
WHERE c.document_id = d.id AND c.tenant_id IS NULL;
ALTER TABLE rag_chunks ALTER COLUMN tenant_id SET DEFAULT 'public';
ALTER TABLE rag_chunks ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS rag_chunks_tenant_product_idx
    ON rag_chunks (tenant_id, canonical_product_id);

DROP POLICY IF EXISTS rag_documents_tenant_read ON rag_documents;
CREATE POLICY rag_documents_tenant_access ON rag_documents
    USING (
        tenant_id = 'public'
        OR current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    )
    WITH CHECK (
        current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    );
ALTER TABLE rag_documents FORCE ROW LEVEL SECURITY;

ALTER TABLE rag_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY rag_chunks_tenant_access ON rag_chunks
    USING (
        tenant_id = 'public'
        OR current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    )
    WITH CHECK (
        current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    );

ALTER TABLE rag_product_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_product_aliases FORCE ROW LEVEL SECURITY;
CREATE POLICY rag_aliases_tenant_access ON rag_product_aliases
    USING (
        tenant_id = 'public'
        OR current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    )
    WITH CHECK (
        current_setting('app.rag_tenant', true) = '*'
        OR tenant_id = current_setting('app.rag_tenant', true)
    );
