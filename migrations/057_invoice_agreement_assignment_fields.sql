ALTER TABLE invoice_agreements
    ADD COLUMN IF NOT EXISTS assignment_scope TEXT NOT NULL DEFAULT '';

ALTER TABLE invoice_agreements
    ADD COLUMN IF NOT EXISTS result_obligation TEXT NOT NULL DEFAULT '';

ALTER TABLE invoice_agreements
    ADD COLUMN IF NOT EXISTS delivery_term TEXT NOT NULL DEFAULT '';
