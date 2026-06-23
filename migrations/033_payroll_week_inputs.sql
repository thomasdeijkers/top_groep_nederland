CREATE TABLE IF NOT EXISTS payroll_week_inputs (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_period_week_id INTEGER REFERENCES payroll_period_weeks(id) ON DELETE SET NULL,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    arrangement_id INTEGER REFERENCES payroll_employee_arrangements(id) ON DELETE SET NULL,
    timesheet_inbox_id INTEGER REFERENCES whatsapp_timesheet_inbox(id) ON DELETE SET NULL,
    week_number INTEGER,
    employee_name TEXT NOT NULL,
    work_date DATE,
    source_channel TEXT NOT NULL DEFAULT 'dashboard',
    parse_source TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'concept',
    worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    day_codes JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_fields JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_week_inputs_timesheet
    ON payroll_week_inputs (timesheet_inbox_id)
    WHERE timesheet_inbox_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payroll_week_inputs_period_week
    ON payroll_week_inputs (payroll_period_id, payroll_period_week_id, status);

CREATE INDEX IF NOT EXISTS idx_payroll_week_inputs_relation
    ON payroll_week_inputs (relation_id, work_date DESC);

CREATE TABLE IF NOT EXISTS payroll_week_input_days (
    id SERIAL PRIMARY KEY,
    payroll_week_input_id INTEGER NOT NULL REFERENCES payroll_week_inputs(id) ON DELETE CASCADE,
    day_index INTEGER NOT NULL CHECK (day_index BETWEEN 1 AND 7),
    day_name TEXT NOT NULL,
    hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    km NUMERIC(10,2) NOT NULL DEFAULT 0,
    day_code TEXT,
    source TEXT NOT NULL DEFAULT 'parsed_fields',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_week_input_id, day_index)
);

CREATE TABLE IF NOT EXISTS payroll_week_input_projects (
    id SERIAL PRIMARY KEY,
    payroll_week_input_id INTEGER NOT NULL REFERENCES payroll_week_inputs(id) ON DELETE CASCADE,
    project_time_booking_id INTEGER REFERENCES project_time_bookings(id) ON DELETE SET NULL,
    principal_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    project_id INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    work_date DATE,
    hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'project_time_bookings',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_week_input_projects_booking
    ON payroll_week_input_projects (project_time_booking_id)
    WHERE project_time_booking_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payroll_week_input_projects_input
    ON payroll_week_input_projects (payroll_week_input_id);

WITH booking_context AS (
    SELECT timesheet_inbox_id,
           MAX(relation_id) AS relation_id,
           SUM(hours) AS booking_hours
    FROM project_time_bookings
    GROUP BY timesheet_inbox_id
), source_rows AS (
    SELECT p.id AS payroll_period_id,
           pw.id AS payroll_period_week_id,
           COALESCE(w.matched_relation_id, b.relation_id) AS relation_id,
           w.id AS timesheet_inbox_id,
           COALESCE(r.name, w.employee_name, w.matched_candidate_name, 'Onbekend') AS employee_name,
           COALESCE(w.work_date, w.received_at::date) AS work_date,
           CASE
               WHEN COALESCE(w.parsed_fields->'week_number'->>'value', '') ~ '^[0-9]+$'
               THEN (w.parsed_fields->'week_number'->>'value')::integer
               ELSE pw.week_number
           END AS week_number,
           COALESCE(w.source_channel, 'dashboard') AS source_channel,
           COALESCE(w.parse_source, 'manual') AS parse_source,
           COALESCE(w.status, 'concept') AS status,
           COALESCE(
               w.hours,
               b.booking_hours,
               CASE
                   WHEN COALESCE(w.parsed_fields->'total_hours'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
                   THEN REPLACE(w.parsed_fields->'total_hours'->>'value', ',', '.')::numeric
                   ELSE 0
               END
           ) AS worked_hours,
           CASE
               WHEN COALESCE(w.parsed_fields->'total_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
               THEN REPLACE(w.parsed_fields->'total_km'->>'value', ',', '.')::numeric
               WHEN COALESCE(w.parsed_fields->'calculated_total_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
               THEN REPLACE(w.parsed_fields->'calculated_total_km'->>'value', ',', '.')::numeric
               ELSE (
                   CASE WHEN COALESCE(w.parsed_fields->'monday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'monday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'tuesday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'tuesday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'wednesday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'wednesday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'thursday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'thursday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'friday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'friday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'saturday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'saturday_km'->>'value', ',', '.')::numeric ELSE 0 END
                 + CASE WHEN COALESCE(w.parsed_fields->'sunday_km'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$' THEN REPLACE(w.parsed_fields->'sunday_km'->>'value', ',', '.')::numeric ELSE 0 END
               )
           END AS total_km,
           jsonb_build_object(
               'monday', COALESCE(w.parsed_fields->'monday_code'->>'value', ''),
               'tuesday', COALESCE(w.parsed_fields->'tuesday_code'->>'value', ''),
               'wednesday', COALESCE(w.parsed_fields->'wednesday_code'->>'value', ''),
               'thursday', COALESCE(w.parsed_fields->'thursday_code'->>'value', ''),
               'friday', COALESCE(w.parsed_fields->'friday_code'->>'value', ''),
               'saturday', COALESCE(w.parsed_fields->'saturday_code'->>'value', ''),
               'sunday', COALESCE(w.parsed_fields->'sunday_code'->>'value', '')
           ) AS day_codes,
           COALESCE(w.parsed_fields, '{}'::jsonb) AS raw_fields
    FROM whatsapp_timesheet_inbox w
    JOIN payroll_periods p
        ON COALESCE(w.work_date, w.received_at::date) BETWEEN p.start_date AND p.end_date
    JOIN payroll_period_weeks pw
        ON pw.payroll_period_id = p.id
       AND COALESCE(w.work_date, w.received_at::date) BETWEEN pw.start_date AND pw.end_date
    LEFT JOIN booking_context b ON b.timesheet_inbox_id = w.id
    LEFT JOIN relations r ON r.id = COALESCE(w.matched_relation_id, b.relation_id)
    WHERE w.deleted_at IS NULL
      AND w.archived_at IS NULL
      AND LOWER(REPLACE(COALESCE(w.status, ''), ' ', '_')) IN ('gevalideerd', 'validated', 'loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
), with_arrangement AS (
    SELECT s.*,
           a.id AS arrangement_id
    FROM source_rows s
    LEFT JOIN LATERAL (
        SELECT candidate.id
        FROM payroll_employee_arrangements candidate
        WHERE candidate.relation_id = s.relation_id
          AND (candidate.valid_from_year < EXTRACT(YEAR FROM s.work_date)::integer
               OR (candidate.valid_from_year = EXTRACT(YEAR FROM s.work_date)::integer
                   AND candidate.valid_from_period_number <= (
                       SELECT pp.period_number FROM payroll_periods pp WHERE pp.id = s.payroll_period_id
                   )))
        ORDER BY candidate.valid_from_year DESC, candidate.valid_from_period_number DESC, candidate.id DESC
        LIMIT 1
    ) a ON TRUE
)
INSERT INTO payroll_week_inputs (
    payroll_period_id,
    payroll_period_week_id,
    relation_id,
    arrangement_id,
    timesheet_inbox_id,
    week_number,
    employee_name,
    work_date,
    source_channel,
    parse_source,
    status,
    worked_hours,
    total_km,
    day_codes,
    raw_fields,
    created_at,
    updated_at
)
SELECT payroll_period_id,
       payroll_period_week_id,
       relation_id,
       arrangement_id,
       timesheet_inbox_id,
       week_number,
       employee_name,
       work_date,
       source_channel,
       parse_source,
       status,
       worked_hours,
       total_km,
       day_codes,
       raw_fields,
       NOW(),
       NOW()
FROM with_arrangement
ON CONFLICT (timesheet_inbox_id) WHERE timesheet_inbox_id IS NOT NULL
DO UPDATE SET
    payroll_period_id = EXCLUDED.payroll_period_id,
    payroll_period_week_id = EXCLUDED.payroll_period_week_id,
    relation_id = EXCLUDED.relation_id,
    arrangement_id = EXCLUDED.arrangement_id,
    week_number = EXCLUDED.week_number,
    employee_name = EXCLUDED.employee_name,
    work_date = EXCLUDED.work_date,
    source_channel = EXCLUDED.source_channel,
    parse_source = EXCLUDED.parse_source,
    status = EXCLUDED.status,
    worked_hours = EXCLUDED.worked_hours,
    total_km = EXCLUDED.total_km,
    day_codes = EXCLUDED.day_codes,
    raw_fields = EXCLUDED.raw_fields,
    updated_at = NOW();

WITH day_source AS (
    SELECT i.id AS payroll_week_input_id,
           d.day_index,
           d.day_name,
           CASE
               WHEN COALESCE(i.raw_fields->d.hours_key->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
               THEN REPLACE(i.raw_fields->d.hours_key->>'value', ',', '.')::numeric
               ELSE 0
           END AS hours,
           CASE
               WHEN COALESCE(i.raw_fields->d.km_key->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
               THEN REPLACE(i.raw_fields->d.km_key->>'value', ',', '.')::numeric
               ELSE 0
           END AS km,
           NULLIF(i.raw_fields->d.code_key->>'value', '') AS day_code
    FROM payroll_week_inputs i
    CROSS JOIN (VALUES
        (1, 'maandag', 'monday_hours', 'monday_km', 'monday_code'),
        (2, 'dinsdag', 'tuesday_hours', 'tuesday_km', 'tuesday_code'),
        (3, 'woensdag', 'wednesday_hours', 'wednesday_km', 'wednesday_code'),
        (4, 'donderdag', 'thursday_hours', 'thursday_km', 'thursday_code'),
        (5, 'vrijdag', 'friday_hours', 'friday_km', 'friday_code'),
        (6, 'zaterdag', 'saturday_hours', 'saturday_km', 'saturday_code'),
        (7, 'zondag', 'sunday_hours', 'sunday_km', 'sunday_code')
    ) AS d(day_index, day_name, hours_key, km_key, code_key)
    WHERE i.timesheet_inbox_id IS NOT NULL
)
INSERT INTO payroll_week_input_days (
    payroll_week_input_id, day_index, day_name, hours, km, day_code, created_at, updated_at
)
SELECT payroll_week_input_id, day_index, day_name, hours, km, day_code, NOW(), NOW()
FROM day_source
ON CONFLICT (payroll_week_input_id, day_index)
DO UPDATE SET
    hours = EXCLUDED.hours,
    km = EXCLUDED.km,
    day_code = EXCLUDED.day_code,
    updated_at = NOW();

INSERT INTO payroll_week_input_projects (
    payroll_week_input_id,
    project_time_booking_id,
    principal_id,
    project_id,
    work_date,
    hours,
    status,
    created_at,
    updated_at
)
SELECT i.id,
       b.id,
       b.principal_id,
       b.project_id,
       b.work_date,
       COALESCE(b.hours, 0),
       COALESCE(b.status, 'concept'),
       NOW(),
       NOW()
FROM project_time_bookings b
JOIN payroll_week_inputs i ON i.timesheet_inbox_id = b.timesheet_inbox_id
ON CONFLICT (project_time_booking_id) WHERE project_time_booking_id IS NOT NULL
DO UPDATE SET
    payroll_week_input_id = EXCLUDED.payroll_week_input_id,
    principal_id = EXCLUDED.principal_id,
    project_id = EXCLUDED.project_id,
    work_date = EXCLUDED.work_date,
    hours = EXCLUDED.hours,
    status = EXCLUDED.status,
    updated_at = NOW();
