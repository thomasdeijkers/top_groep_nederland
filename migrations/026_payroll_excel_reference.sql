CREATE TABLE IF NOT EXISTS payroll_employees (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'actief',
    source TEXT NOT NULL DEFAULT 'dashboard',
    imported_from TEXT,
    reviewed_by TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (relation_id, employee_name)
);

CREATE TABLE IF NOT EXISTS payroll_employee_settings (
    id SERIAL PRIMARY KEY,
    payroll_employee_id INTEGER REFERENCES payroll_employees(id) ON DELETE CASCADE,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    contract_hours NUMERIC(10,2),
    cao_name TEXT,
    phase TEXT,
    pension_scheme TEXT,
    license_plate TEXT,
    choice_budget TEXT,
    function_name TEXT,
    gross_hourly_wage NUMERIC(12,4),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'dashboard',
    imported_from TEXT,
    reviewed_by TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_employee_id, payroll_period_id)
);

CREATE TABLE IF NOT EXISTS payroll_week_entries (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_period_week_id INTEGER REFERENCES payroll_period_weeks(id) ON DELETE SET NULL,
    payroll_employee_id INTEGER REFERENCES payroll_employees(id) ON DELETE SET NULL,
    timesheet_inbox_id INTEGER REFERENCES whatsapp_timesheet_inbox(id) ON DELETE SET NULL,
    project_time_booking_id INTEGER REFERENCES project_time_bookings(id) ON DELETE SET NULL,
    week_number INTEGER NOT NULL,
    employee_name TEXT NOT NULL,
    contract_hours NUMERIC(10,2),
    worked_days NUMERIC(10,2) NOT NULL DEFAULT 0,
    worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    vacation_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    sickness_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    rv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    kv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    holiday_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    commute_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    work_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    fuel_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    extra_reimbursement NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_advance NUMERIC(12,2) NOT NULL DEFAULT 0,
    project_info TEXT,
    remarks TEXT,
    status TEXT NOT NULL DEFAULT 'parsed',
    source TEXT NOT NULL DEFAULT 'dashboard',
    imported_from TEXT,
    reviewed_by TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payroll_period_totals (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_employee_id INTEGER REFERENCES payroll_employees(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    total_worked_days NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_vacation_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_sickness_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_rv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_kv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_holiday_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_declarations NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_net_advance NUMERIC(12,2) NOT NULL DEFAULT 0,
    already_received_net NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_to_receive NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_period_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    wkr_reimbursements NUMERIC(12,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'dashboard',
    imported_from TEXT,
    reviewed_by TEXT,
    calculation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_period_id, employee_name)
);

CREATE TABLE IF NOT EXISTS payroll_calculation_rules (
    id SERIAL PRIMARY KEY,
    rule_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'excel',
    expression TEXT,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'excel_reference',
    imported_from TEXT,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payroll_calculation_results (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_employee_id INTEGER REFERENCES payroll_employees(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    result_key TEXT NOT NULL,
    dashboard_value NUMERIC(14,4),
    excel_value NUMERIC(14,4),
    difference NUMERIC(14,4),
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'dashboard',
    imported_from TEXT,
    reviewed_by TEXT,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payroll_import_logs (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE SET NULL,
    import_type TEXT NOT NULL DEFAULT 'excel_reference',
    filename TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'excel',
    imported_from TEXT,
    status TEXT NOT NULL DEFAULT 'concept',
    sheet_names JSONB NOT NULL DEFAULT '[]'::jsonb,
    mapped_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    formulas JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    imported_rows INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payroll_week_entries_period
    ON payroll_week_entries (payroll_period_id, week_number);

CREATE INDEX IF NOT EXISTS idx_payroll_period_totals_period
    ON payroll_period_totals (payroll_period_id);

CREATE INDEX IF NOT EXISTS idx_payroll_calculation_results_period
    ON payroll_calculation_results (payroll_period_id, employee_name);

CREATE INDEX IF NOT EXISTS idx_payroll_import_logs_period
    ON payroll_import_logs (payroll_period_id, created_at DESC);
