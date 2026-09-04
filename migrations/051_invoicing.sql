CREATE TABLE IF NOT EXISTS invoice_runs (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    week_number INTEGER NOT NULL CHECK (week_number BETWEEN 1 AND 53),
    invoice_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'concept' CHECK (status IN ('concept', 'definitief', 'verzonden')),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_runs_period
    ON invoice_runs (year DESC, week_number DESC, id DESC);

CREATE TABLE IF NOT EXISTS invoice_inputs (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES invoice_runs(id) ON DELETE CASCADE,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL DEFAULT '',
    principal_name TEXT NOT NULL DEFAULT '',
    project_name TEXT NOT NULL DEFAULT '',
    project_reference TEXT NOT NULL DEFAULT '',
    project_location TEXT NOT NULL DEFAULT '',
    regime TEXT NOT NULL DEFAULT 'regie' CHECK (regime IN ('regie', 'aangenomen werk')),
    hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    hourly_rate NUMERIC(12,2) NOT NULL DEFAULT 0,
    agreed_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    labor_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    parking_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
    material_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
    other_sales_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
    olympus_costs NUMERIC(12,2) NOT NULL DEFAULT 0,
    olympus_cost_description TEXT NOT NULL DEFAULT 'Olympus-kosten',
    sales_vat_rate NUMERIC(5,2) NOT NULL DEFAULT 0,
    fee_percent NUMERIC(5,2) NOT NULL DEFAULT 13.25,
    services TEXT NOT NULL DEFAULT 'a,b,c,d',
    sepa_active BOOLEAN NOT NULL DEFAULT TRUE,
    factoring BOOLEAN NOT NULL DEFAULT FALSE,
    factoring_company TEXT NOT NULL DEFAULT 'Pronkert Factoring B.V.',
    factoring_iban TEXT NOT NULL DEFAULT '',
    factoring_address TEXT NOT NULL DEFAULT '',
    factoring_city TEXT NOT NULL DEFAULT '',
    factoring_email TEXT NOT NULL DEFAULT '',
    factoring_phone TEXT NOT NULL DEFAULT '',
    factoring_kvk TEXT NOT NULL DEFAULT '',
    supplier_invoice_number TEXT NOT NULL DEFAULT '',
    supplier_invoice_suffix TEXT NOT NULL DEFAULT '',
    payment_term_days INTEGER NOT NULL DEFAULT 30,
    source_type TEXT NOT NULL DEFAULT 'handmatig',
    status TEXT NOT NULL DEFAULT 'concept' CHECK (status IN ('concept', 'gevalideerd', 'gefactureerd')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_inputs_run
    ON invoice_inputs (run_id, id);

CREATE TABLE IF NOT EXISTS invoice_outputs (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES invoice_runs(id) ON DELETE CASCADE,
    input_id INTEGER NOT NULL REFERENCES invoice_inputs(id) ON DELETE CASCADE,
    stream TEXT NOT NULL CHECK (stream IN ('verkoop', 'olympus')),
    invoice_number TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'concept' CHECK (status IN ('concept', 'definitief', 'verzonden')),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, input_id, stream)
);

CREATE INDEX IF NOT EXISTS idx_invoice_outputs_run
    ON invoice_outputs (run_id, input_id, stream);

CREATE TABLE IF NOT EXISTS invoice_number_sequences (
    sequence_key TEXT PRIMARY KEY,
    next_number BIGINT NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

INSERT INTO invoice_number_sequences (sequence_key, next_number)
VALUES ('olympus', 50083)
ON CONFLICT (sequence_key) DO NOTHING;
