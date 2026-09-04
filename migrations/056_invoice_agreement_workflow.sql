ALTER TABLE invoice_runs
    DROP CONSTRAINT IF EXISTS invoice_runs_status_check;

ALTER TABLE invoice_runs
    ADD CONSTRAINT invoice_runs_status_check
    CHECK (status IN ('concept', 'definitief', 'verzonden', 'archief'));

CREATE TABLE IF NOT EXISTS invoice_agreements (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE RESTRICT,
    principal_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE RESTRICT,
    project_id INTEGER NOT NULL REFERENCES vacancies(id) ON DELETE RESTRICT,
    regime TEXT NOT NULL DEFAULT 'regie' CHECK (regime IN ('regie', 'aangenomen werk')),
    hourly_rate NUMERIC(12, 2) NOT NULL DEFAULT 0,
    start_date DATE NOT NULL,
    end_date DATE,
    status TEXT NOT NULL DEFAULT 'concept' CHECK (status IN ('concept', 'verzonden', 'getekend', 'beeindigd')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_agreements_active
    ON invoice_agreements (relation_id, principal_id, project_id, status, start_date DESC);

ALTER TABLE invoice_inputs
    ADD COLUMN IF NOT EXISTS agreement_id INTEGER REFERENCES invoice_agreements(id) ON DELETE SET NULL;

ALTER TABLE invoice_documents
    ADD COLUMN IF NOT EXISTS agreement_id INTEGER REFERENCES invoice_agreements(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_invoice_documents_agreement
    ON invoice_documents (agreement_id, created_at DESC);
