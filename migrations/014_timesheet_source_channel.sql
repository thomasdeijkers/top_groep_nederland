ALTER TABLE whatsapp_timesheet_inbox
    ADD COLUMN IF NOT EXISTS source_channel TEXT NOT NULL DEFAULT 'manual_upload';

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_source_channel
    ON whatsapp_timesheet_inbox (source_channel);
