-- Production document lifecycle and tenant isolation controls.
-- Public YAFA catalogue rows remain tenant_id='public'. Private knowledge
-- must be queried with a matching tenant_id by the service role.

ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'public';
ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE rag_documents ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS rag_documents_active_tenant_idx
    ON rag_documents (tenant_id, canonical_product_id) WHERE is_active;

ALTER TABLE rag_documents DROP CONSTRAINT IF EXISTS rag_documents_canonical_product_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS rag_documents_tenant_product_unique
    ON rag_documents (tenant_id, canonical_product_id);

ALTER TABLE rag_product_aliases ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT 'public';
ALTER TABLE rag_product_aliases DROP CONSTRAINT IF EXISTS rag_product_aliases_canonical_product_id_normalized_alias_key;
CREATE UNIQUE INDEX IF NOT EXISTS rag_aliases_tenant_product_unique
    ON rag_product_aliases (tenant_id, canonical_product_id, normalized_alias);

-- Defense in depth: use a non-owner runtime role with no BYPASSRLS privilege.
ALTER TABLE rag_documents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rag_documents_tenant_read ON rag_documents;
CREATE POLICY rag_documents_tenant_read ON rag_documents
    USING (tenant_id = 'public' OR tenant_id = current_setting('app.rag_tenant', true));
