ALTER TABLE whatsapp_timesheet_inbox
    ADD COLUMN IF NOT EXISTS selected_principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS selected_project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP WITHOUT TIME ZONE,
    ADD COLUMN IF NOT EXISTS payroll_sent_at TIMESTAMP WITHOUT TIME ZONE;

CREATE TABLE IF NOT EXISTS project_time_bookings (
    id SERIAL PRIMARY KEY,
    timesheet_inbox_id INTEGER NOT NULL REFERENCES whatsapp_timesheet_inbox(id) ON DELETE CASCADE,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    work_date DATE,
    hours NUMERIC,
    status TEXT NOT NULL DEFAULT 'loon_te_berekenen',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_status
    ON project_time_bookings (status);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_timesheet
    ON project_time_bookings (timesheet_inbox_id);
