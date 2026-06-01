ALTER TABLE whatsapp_timesheet_inbox
    ADD COLUMN IF NOT EXISTS media_path TEXT,
    ADD COLUMN IF NOT EXISTS parse_source TEXT NOT NULL DEFAULT 'manual_upload';
