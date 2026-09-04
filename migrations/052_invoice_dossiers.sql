ALTER TABLE relations ADD COLUMN IF NOT EXISTS logo_filename TEXT;
ALTER TABLE relations ADD COLUMN IF NOT EXISTS logo_path TEXT;

CREATE TABLE IF NOT EXISTS invoice_brand_assets (
    asset_key TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS invoice_documents (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    run_id INTEGER REFERENCES invoice_runs(id) ON DELETE SET NULL,
    input_id INTEGER REFERENCES invoice_inputs(id) ON DELETE SET NULL,
    output_id INTEGER REFERENCES invoice_outputs(id) ON DELETE SET NULL,
    document_type TEXT NOT NULL DEFAULT 'overig',
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_documents_relation ON invoice_documents (relation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invoice_documents_search ON invoice_documents (LOWER(filename), document_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_invoice_documents_output_type
    ON invoice_documents (output_id, document_type)
    WHERE output_id IS NOT NULL;
