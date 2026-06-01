ALTER TABLE whatsapp_timesheet_inbox
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITHOUT TIME ZONE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITHOUT TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_archived_at
    ON whatsapp_timesheet_inbox (archived_at);

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_deleted_at
    ON whatsapp_timesheet_inbox (deleted_at);
