ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS timesheet_inbox_id INTEGER REFERENCES whatsapp_timesheet_inbox(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payroll_year_id INTEGER REFERENCES payroll_years(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payroll_period_week_id INTEGER REFERENCES payroll_period_weeks(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payroll_week_input_id INTEGER REFERENCES payroll_week_inputs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS correlation_id TEXT,
    ADD COLUMN IF NOT EXISTS source_channel TEXT;

UPDATE audit_events e
SET relation_id = COALESCE(e.relation_id, NULLIF(e.metadata->>'relation_id', '')::integer)
WHERE e.relation_id IS NULL
  AND e.metadata ? 'relation_id'
  AND (e.metadata->>'relation_id') ~ '^[0-9]+$';

UPDATE audit_events e
SET timesheet_inbox_id = e.entity_id
WHERE e.timesheet_inbox_id IS NULL
  AND e.entity_type IN ('urenbriefje', 'whatsapp_timesheet')
  AND e.entity_id IS NOT NULL;

UPDATE audit_events e
SET relation_id = e.entity_id
WHERE e.relation_id IS NULL
  AND e.entity_type IN ('relatie', 'candidate', 'principal')
  AND e.entity_id IS NOT NULL;

UPDATE audit_events e
SET payroll_period_id = e.entity_id
WHERE e.payroll_period_id IS NULL
  AND e.entity_type IN ('periode', 'payroll_period')
  AND e.entity_id IS NOT NULL;

UPDATE audit_events e
SET payroll_period_id = NULLIF(e.metadata->>'payroll_period_id', '')::integer
WHERE e.payroll_period_id IS NULL
  AND e.metadata ? 'payroll_period_id'
  AND (e.metadata->>'payroll_period_id') ~ '^[0-9]+$';

UPDATE audit_events e
SET payroll_week_input_id = NULLIF(e.metadata->>'payroll_week_input_id', '')::integer
WHERE e.payroll_week_input_id IS NULL
  AND e.metadata ? 'payroll_week_input_id'
  AND (e.metadata->>'payroll_week_input_id') ~ '^[0-9]+$';

UPDATE audit_events e
SET payroll_period_id = i.payroll_period_id,
    payroll_period_week_id = i.payroll_period_week_id,
    relation_id = COALESCE(e.relation_id, i.relation_id)
FROM payroll_week_inputs i
WHERE e.payroll_week_input_id = i.id
  AND (e.payroll_period_id IS NULL OR e.payroll_period_week_id IS NULL OR e.relation_id IS NULL);

UPDATE audit_events e
SET payroll_period_id = b.payroll_period_id,
    relation_id = COALESCE(e.relation_id, b.relation_id)
FROM project_time_bookings b
WHERE e.timesheet_inbox_id = b.timesheet_inbox_id
  AND (e.payroll_period_id IS NULL OR e.relation_id IS NULL);

UPDATE audit_events e
SET payroll_year_id = p.payroll_year_id
FROM payroll_periods p
WHERE e.payroll_period_id = p.id
  AND e.payroll_year_id IS NULL;

UPDATE openai_api_audit_events a
SET purpose = COALESCE(a.purpose, 'timesheet_ocr'),
    timesheet_inbox_id = COALESCE(a.timesheet_inbox_id, a.source_id)
WHERE a.source IN ('whatsapp_timesheet', 'whatsapp_timesheet_reparse')
  AND a.source_id IS NOT NULL;

UPDATE openai_api_audit_events a
SET relation_id = COALESCE(a.relation_id, w.matched_relation_id)
FROM whatsapp_timesheet_inbox w
WHERE a.timesheet_inbox_id = w.id
  AND a.relation_id IS NULL;

UPDATE openai_api_audit_events a
SET payroll_week_input_id = i.id
FROM payroll_week_inputs i
WHERE a.timesheet_inbox_id = i.timesheet_inbox_id
  AND a.payroll_week_input_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_audit_events_payroll_period
    ON audit_events (payroll_period_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_relation
    ON audit_events (relation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_timesheet
    ON audit_events (timesheet_inbox_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_events_correlation
    ON audit_events (correlation_id)
    WHERE correlation_id IS NOT NULL;

CREATE OR REPLACE VIEW payroll_audit_context AS
SELECT e.id,
       e.created_at,
       e.actor_name,
       e.action,
       e.entity_type,
       e.entity_id,
       e.status,
       e.relation_id,
       r.name AS relation_name,
       e.timesheet_inbox_id,
       e.payroll_year_id,
       y.year,
       e.payroll_period_id,
       p.period_number,
       p.name AS payroll_period_name,
       e.payroll_period_week_id,
       w.week_number,
       e.payroll_week_input_id,
       e.correlation_id,
       e.source_channel,
       e.metadata
FROM audit_events e
LEFT JOIN relations r ON r.id = e.relation_id
LEFT JOIN payroll_years y ON y.id = e.payroll_year_id
LEFT JOIN payroll_periods p ON p.id = e.payroll_period_id
LEFT JOIN payroll_period_weeks w ON w.id = e.payroll_period_week_id;

CREATE OR REPLACE VIEW payroll_ai_ocr_audit_context AS
SELECT a.id,
       a.created_at,
       a.provider,
       COALESCE(a.purpose, 'timesheet_ocr') AS purpose,
       a.source,
       a.source_id,
       a.model,
       a.endpoint,
       a.status_code,
       a.error,
       a.relation_id,
       r.name AS relation_name,
       a.timesheet_inbox_id,
       a.payroll_week_input_id,
       i.payroll_period_id,
       p.period_number,
       p.name AS payroll_period_name,
       i.payroll_period_week_id,
       w.week_number,
       a.total_tokens,
       a.latency_ms
FROM openai_api_audit_events a
LEFT JOIN relations r ON r.id = a.relation_id
LEFT JOIN payroll_week_inputs i ON i.id = a.payroll_week_input_id
LEFT JOIN payroll_periods p ON p.id = i.payroll_period_id
LEFT JOIN payroll_period_weeks w ON w.id = i.payroll_period_week_id;

CREATE OR REPLACE VIEW payroll_period_audit_summary AS
SELECT p.id AS payroll_period_id,
       p.year,
       p.period_number,
       p.name AS payroll_period_name,
       COUNT(DISTINCT e.id) AS audit_event_count,
       COUNT(DISTINCT a.id) AS ai_ocr_audit_event_count,
       MAX(e.created_at) AS last_audit_at,
       MAX(a.created_at) AS last_ai_ocr_audit_at
FROM payroll_periods p
LEFT JOIN audit_events e ON e.payroll_period_id = p.id
LEFT JOIN payroll_week_inputs i ON i.payroll_period_id = p.id
LEFT JOIN openai_api_audit_events a ON a.payroll_week_input_id = i.id
GROUP BY p.id, p.year, p.period_number, p.name;

INSERT INTO audit_events (
    actor_name,
    action,
    entity_type,
    entity_label,
    description,
    status,
    metadata,
    created_at
)
SELECT
    'Admin',
    'Payroll auditcontext toegevoegd',
    'payroll_datamodel',
    'Audit-koppellaag',
    'Auditregels en AI/OCR-auditregels kunnen nu aan relatie, urenbriefje, loonjaar, loonperiode en loonweek worden gekoppeld.',
    'Systeem',
    jsonb_build_object(
        'views', jsonb_build_array('payroll_audit_context', 'payroll_ai_ocr_audit_context', 'payroll_period_audit_summary'),
        'source', 'migrations/042_payroll_audit_context.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Payroll auditcontext toegevoegd'
      AND entity_type = 'payroll_datamodel'
);
