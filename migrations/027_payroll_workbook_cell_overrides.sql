CREATE TABLE IF NOT EXISTS payroll_workbook_cell_overrides (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
    tab_label TEXT NOT NULL,
    row_key TEXT NOT NULL,
    employee_name TEXT,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    column_key TEXT NOT NULL,
    column_label TEXT NOT NULL,
    original_value TEXT,
    previous_value TEXT,
    value TEXT,
    source TEXT NOT NULL DEFAULT 'dashboard',
    reviewed_by TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_period_id, tab_label, row_key, column_key)
);

CREATE INDEX IF NOT EXISTS idx_payroll_workbook_cell_overrides_period
    ON payroll_workbook_cell_overrides (payroll_period_id, tab_label, row_key);

CREATE INDEX IF NOT EXISTS idx_payroll_workbook_cell_overrides_relation
    ON payroll_workbook_cell_overrides (relation_id, updated_at DESC);
