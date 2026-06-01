CREATE TABLE IF NOT EXISTS whatsapp_timesheet_inbox (
    id SERIAL PRIMARY KEY,
    sender_name TEXT,
    sender_phone TEXT NOT NULL,
    message_text TEXT,
    media_filename TEXT,
    media_path TEXT,
    parse_source TEXT NOT NULL DEFAULT 'manual_upload',
    status TEXT NOT NULL DEFAULT 'nieuw',
    matched_candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
    matched_candidate_name TEXT,
    employee_name TEXT,
    employee_address TEXT,
    employee_postal_code TEXT,
    employee_city TEXT,
    principal_name TEXT,
    project_name TEXT,
    work_date DATE,
    hours NUMERIC,
    break_minutes INTEGER,
    parsed_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    overall_confidence NUMERIC,
    received_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_sender_phone
    ON whatsapp_timesheet_inbox (sender_phone);

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_status
    ON whatsapp_timesheet_inbox (status);
