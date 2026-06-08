ALTER TABLE relations
    ADD COLUMN IF NOT EXISTS payroll_license_plate TEXT,
    ADD COLUMN IF NOT EXISTS payroll_choice_budget TEXT,
    ADD COLUMN IF NOT EXISTS payroll_phase TEXT,
    ADD COLUMN IF NOT EXISTS payroll_pension TEXT,
    ADD COLUMN IF NOT EXISTS payroll_cao_hours TEXT,
    ADD COLUMN IF NOT EXISTS payroll_days_right TEXT,
    ADD COLUMN IF NOT EXISTS payroll_scale TEXT,
    ADD COLUMN IF NOT EXISTS payroll_function TEXT,
    ADD COLUMN IF NOT EXISTS payroll_hourly_wage TEXT,
    ADD COLUMN IF NOT EXISTS payroll_settings_updated_at TIMESTAMP WITHOUT TIME ZONE;
