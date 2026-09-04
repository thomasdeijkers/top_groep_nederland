CREATE TABLE IF NOT EXISTS mediation_agreements (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE RESTRICT,
    start_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'getekend' CHECK (status IN ('concept', 'verzonden', 'getekend', 'beeindigd')),
    services TEXT NOT NULL DEFAULT 'a,b,c,d',
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mediation_agreements_relation
    ON mediation_agreements (relation_id, start_date DESC);

ALTER TABLE invoice_documents
    ADD COLUMN IF NOT EXISTS mediation_agreement_id INTEGER REFERENCES mediation_agreements(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_invoice_documents_mediation_agreement
    ON invoice_documents (mediation_agreement_id, created_at DESC);
