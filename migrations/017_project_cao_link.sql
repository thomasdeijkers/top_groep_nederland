ALTER TABLE vacancies
    ADD COLUMN IF NOT EXISTS payroll_cao_setting_id INTEGER REFERENCES payroll_cao_settings(id) ON DELETE SET NULL;

ALTER TABLE project_time_bookings
    ADD COLUMN IF NOT EXISTS payroll_cao_setting_id INTEGER REFERENCES payroll_cao_settings(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_vacancies_payroll_cao_setting
    ON vacancies (payroll_cao_setting_id);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_payroll_cao_setting
    ON project_time_bookings (payroll_cao_setting_id);
