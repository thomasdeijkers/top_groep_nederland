CREATE TABLE IF NOT EXISTS payroll_cao_settings (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    version_label TEXT,
    effective_from DATE,
    effective_until DATE,
    standard_week_hours NUMERIC,
    overtime_after_hours NUMERIC,
    weekday_overtime_percent NUMERIC,
    saturday_percent NUMERIC,
    sunday_percent NUMERIC,
    holiday_percent NUMERIC,
    travel_cost_per_km NUMERIC,
    default_hourly_wage NUMERIC,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'manual',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payroll_cao_settings_status
    ON payroll_cao_settings (status);

CREATE INDEX IF NOT EXISTS idx_payroll_cao_settings_effective_from
    ON payroll_cao_settings (effective_from);
