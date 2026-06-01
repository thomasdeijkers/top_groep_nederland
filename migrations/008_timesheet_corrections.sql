CREATE TABLE IF NOT EXISTS timesheet_field_corrections (
    id SERIAL PRIMARY KEY,
    timesheet_inbox_id INTEGER NOT NULL REFERENCES whatsapp_timesheet_inbox(id) ON DELETE CASCADE,
    field_key TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT NOT NULL,
    original_confidence NUMERIC,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timesheet_field_corrections_inbox
    ON timesheet_field_corrections (timesheet_inbox_id);
