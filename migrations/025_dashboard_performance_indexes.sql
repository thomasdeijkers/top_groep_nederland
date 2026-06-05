CREATE INDEX IF NOT EXISTS idx_relations_active_type_status
    ON relations (relation_type, status, updated_at DESC)
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_relations_status_lower
    ON relations (LOWER(COALESCE(status, '')))
    WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_vacancies_project_updated
    ON vacancies ((raw_data->>'record_type'), updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_vacancies_status_updated
    ON vacancies (status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_project_recent
    ON project_time_bookings (project_id, work_date DESC, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_project_time_bookings_period_date
    ON project_time_bookings (payroll_period_id, work_date);

CREATE INDEX IF NOT EXISTS idx_payroll_periods_status_dates
    ON payroll_periods (status, start_date DESC, end_date DESC, year DESC, period_number DESC);

CREATE INDEX IF NOT EXISTS idx_payroll_period_weeks_period
    ON payroll_period_weeks (payroll_period_id, week_index);

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_active_received
    ON whatsapp_timesheet_inbox (received_at DESC, id DESC)
    WHERE deleted_at IS NULL AND archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_whatsapp_timesheet_status_active
    ON whatsapp_timesheet_inbox (LOWER(COALESCE(status, '')))
    WHERE deleted_at IS NULL AND archived_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_openai_usage_created_at
    ON openai_usage_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_otys_usage_created_at
    ON otys_api_usage_events (created_at DESC);
