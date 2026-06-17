CREATE TABLE IF NOT EXISTS payroll_years (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL UNIQUE,
    period_count INTEGER NOT NULL DEFAULT 13 CHECK (period_count = 13),
    weeks_per_period INTEGER NOT NULL DEFAULT 4 CHECK (weeks_per_period = 4),
    status TEXT NOT NULL DEFAULT 'concept',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

INSERT INTO payroll_years (year, status, notes, created_at, updated_at)
SELECT DISTINCT p.year,
       'active',
       'Loonjaar met 13 periodes van 4 weken.',
       NOW(),
       NOW()
FROM payroll_periods p
ON CONFLICT (year)
DO UPDATE SET
    period_count = 13,
    weeks_per_period = 4,
    updated_at = NOW();

INSERT INTO payroll_years (year, status, notes, created_at, updated_at)
VALUES (2026, 'active', 'Startjaar uit TGN-leeswijzer en referentiebestand.', NOW(), NOW())
ON CONFLICT (year)
DO NOTHING;

ALTER TABLE payroll_periods
    ADD COLUMN IF NOT EXISTS payroll_year_id INTEGER REFERENCES payroll_years(id) ON DELETE RESTRICT;

UPDATE payroll_periods p
SET payroll_year_id = y.id,
    updated_at = NOW()
FROM payroll_years y
WHERE y.year = p.year
  AND p.payroll_year_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_payroll_periods_year_id
    ON payroll_periods (payroll_year_id, period_number);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_payroll_periods_period_number_13'
    ) THEN
        ALTER TABLE payroll_periods
            ADD CONSTRAINT chk_payroll_periods_period_number_13
            CHECK (period_number BETWEEN 1 AND 13);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS payroll_week_lines (
    id SERIAL PRIMARY KEY,
    payroll_week_input_id INTEGER NOT NULL REFERENCES payroll_week_inputs(id) ON DELETE CASCADE,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_period_week_id INTEGER REFERENCES payroll_period_weeks(id) ON DELETE SET NULL,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    arrangement_id INTEGER REFERENCES payroll_employee_arrangements(id) ON DELETE SET NULL,
    line_index INTEGER NOT NULL DEFAULT 1,
    work_date DATE,
    principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    cost_center TEXT,
    day_code TEXT,
    worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    vacation_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    sickness_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    rv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    kv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    holiday_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    kilometers NUMERIC(10,2) NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'dashboard',
    status TEXT NOT NULL DEFAULT 'concept',
    raw_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_week_input_id, line_index)
);

CREATE INDEX IF NOT EXISTS idx_payroll_week_lines_period_week
    ON payroll_week_lines (payroll_period_id, payroll_period_week_id, status);

CREATE INDEX IF NOT EXISTS idx_payroll_week_lines_relation
    ON payroll_week_lines (relation_id, work_date DESC);

CREATE INDEX IF NOT EXISTS idx_payroll_week_lines_project
    ON payroll_week_lines (principal_id, project_id);

INSERT INTO payroll_week_lines (
    payroll_week_input_id,
    payroll_period_id,
    payroll_period_week_id,
    relation_id,
    arrangement_id,
    line_index,
    work_date,
    principal_id,
    project_id,
    worked_hours,
    source,
    status,
    created_at,
    updated_at
)
SELECT p.payroll_week_input_id,
       i.payroll_period_id,
       i.payroll_period_week_id,
       i.relation_id,
       i.arrangement_id,
       ROW_NUMBER() OVER (PARTITION BY p.payroll_week_input_id ORDER BY p.id),
       p.work_date,
       p.principal_id,
       p.project_id,
       p.hours,
       p.source,
       p.status,
       NOW(),
       NOW()
FROM payroll_week_input_projects p
JOIN payroll_week_inputs i ON i.id = p.payroll_week_input_id
ON CONFLICT (payroll_week_input_id, line_index)
DO UPDATE SET
    payroll_period_id = EXCLUDED.payroll_period_id,
    payroll_period_week_id = EXCLUDED.payroll_period_week_id,
    relation_id = EXCLUDED.relation_id,
    arrangement_id = EXCLUDED.arrangement_id,
    work_date = EXCLUDED.work_date,
    principal_id = EXCLUDED.principal_id,
    project_id = EXCLUDED.project_id,
    worked_hours = EXCLUDED.worked_hours,
    source = EXCLUDED.source,
    status = EXCLUDED.status,
    updated_at = NOW();

INSERT INTO payroll_week_lines (
    payroll_week_input_id,
    payroll_period_id,
    payroll_period_week_id,
    relation_id,
    arrangement_id,
    line_index,
    work_date,
    day_code,
    worked_hours,
    kilometers,
    source,
    status,
    raw_fields,
    created_at,
    updated_at
)
SELECT i.id,
       i.payroll_period_id,
       i.payroll_period_week_id,
       i.relation_id,
       i.arrangement_id,
       1,
       i.work_date,
       NULLIF(NULLIF(i.day_codes::text, '{}'), ''),
       i.worked_hours,
       i.total_km,
       i.parse_source,
       i.status,
       i.raw_fields,
       NOW(),
       NOW()
FROM payroll_week_inputs i
WHERE NOT EXISTS (
    SELECT 1
    FROM payroll_week_lines existing
    WHERE existing.payroll_week_input_id = i.id
)
ON CONFLICT (payroll_week_input_id, line_index)
DO NOTHING;

ALTER TABLE openai_api_audit_events
    ADD COLUMN IF NOT EXISTS provider TEXT NOT NULL DEFAULT 'openai',
    ADD COLUMN IF NOT EXISTS purpose TEXT,
    ADD COLUMN IF NOT EXISTS relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS timesheet_inbox_id INTEGER REFERENCES whatsapp_timesheet_inbox(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payroll_week_input_id INTEGER REFERENCES payroll_week_inputs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS request_hash TEXT,
    ADD COLUMN IF NOT EXISTS response_hash TEXT,
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS total_tokens INTEGER,
    ADD COLUMN IF NOT EXISTS latency_ms INTEGER;

CREATE INDEX IF NOT EXISTS idx_openai_api_audit_provider_purpose
    ON openai_api_audit_events (provider, purpose, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_openai_api_audit_timesheet
    ON openai_api_audit_events (timesheet_inbox_id, payroll_week_input_id);

CREATE INDEX IF NOT EXISTS idx_openai_api_audit_relation
    ON openai_api_audit_events (relation_id, created_at DESC);

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
    'Payroll fundament uitgebreid',
    'payroll_datamodel',
    'Jaar, weekregels en AI/OCR-audit',
    'Datamodel uitgebreid met payroll_years, payroll_week_lines en aanvullende AI/OCR-auditvelden.',
    'Systeem',
    jsonb_build_object(
        'periods_per_year', 13,
        'weeks_per_period', 4,
        'source', 'migrations/037_payroll_datamodel_foundation.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Payroll fundament uitgebreid'
      AND entity_type = 'payroll_datamodel'
);
