WITH missing_periods AS (
    SELECT n.period_number,
           ROW_NUMBER() OVER (ORDER BY n.period_number) AS seed_index
    FROM generate_series(1, 13) AS n(period_number)
    WHERE NOT EXISTS (
        SELECT 1
        FROM payroll_periods p
        WHERE p.year = 2026
          AND p.period_number = n.period_number
    )
), anchor AS (
    SELECT COALESCE(MAX(end_date) + INTERVAL '1 day', DATE '2026-01-05')::date AS first_start_date
    FROM payroll_periods
    WHERE year = 2026
)
INSERT INTO payroll_periods (
    year,
    period_number,
    name,
    start_date,
    end_date,
    status,
    notes,
    created_at,
    updated_at
)
SELECT 2026,
       m.period_number,
       'Periode ' || LPAD(m.period_number::text, 2, '0') || ' testjaar 2026',
       (a.first_start_date + ((m.seed_index - 1) * 28) * INTERVAL '1 day')::date,
       (a.first_start_date + (((m.seed_index - 1) * 28) + 27) * INTERVAL '1 day')::date,
       'open',
       'Automatisch aangemaakte testperiode om het volledige loonjaar zichtbaar te maken.',
       NOW(),
       NOW()
FROM missing_periods m
CROSS JOIN anchor a
ON CONFLICT (year, period_number)
DO NOTHING;
INSERT INTO payroll_period_weeks (
    payroll_period_id,
    week_index,
    week_number,
    start_date,
    end_date,
    created_at,
    updated_at
)
SELECT p.id,
       week_data.week_index,
       EXTRACT(WEEK FROM (p.start_date + ((week_data.week_index - 1) * 7) * INTERVAL '1 day'))::integer,
       (p.start_date + ((week_data.week_index - 1) * 7) * INTERVAL '1 day')::date,
       (p.start_date + (((week_data.week_index - 1) * 7) + 6) * INTERVAL '1 day')::date,
       NOW(),
       NOW()
FROM payroll_periods p
CROSS JOIN generate_series(1, 4) AS week_data(week_index)
WHERE p.year = 2026
ON CONFLICT (payroll_period_id, week_index)
DO NOTHING;

WITH candidate_seed AS (
    SELECT id,
           name,
           phone,
           ROW_NUMBER() OVER (ORDER BY name, id) AS candidate_index
    FROM relations
    WHERE relation_type = 'candidate'
      AND archived_at IS NULL
      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'verwijderd')
    ORDER BY name, id
    LIMIT 8
), default_principal AS (
    SELECT id, name
    FROM relations
    WHERE relation_type = 'principal'
      AND archived_at IS NULL
    ORDER BY id
    LIMIT 1
), default_project AS (
    SELECT id, title, payroll_cao_setting_id
    FROM vacancies
    WHERE COALESCE(raw_data->>'record_type', 'vacancy') = 'project'
    ORDER BY id
    LIMIT 1
), timesheet_seed AS (
    SELECT p.id AS payroll_period_id,
           p.period_number,
           w.id AS payroll_period_week_id,
           w.week_index,
           w.week_number,
           w.start_date AS week_start,
           c.id AS relation_id,
           c.name AS employee_name,
           COALESCE(NULLIF(c.phone, ''), '+31 6 0000 0000') AS sender_phone,
           c.candidate_index,
           (w.start_date + ((c.candidate_index - 1) % 5) * INTERVAL '1 day')::date AS work_date,
           (32 + ((c.candidate_index + w.week_index + p.period_number) % 5))::numeric AS hours,
           principal.id AS principal_id,
           COALESCE(principal.name, 'Test opdrachtgever') AS principal_name,
           project.id AS project_id,
           COALESCE(project.title, 'Test project') AS project_name,
           project.payroll_cao_setting_id
    FROM payroll_periods p
    JOIN payroll_period_weeks w ON w.payroll_period_id = p.id
    CROSS JOIN candidate_seed c
    LEFT JOIN default_principal principal ON TRUE
    LEFT JOIN default_project project ON TRUE
    WHERE p.year = 2026
), inserted_timesheets AS (
    INSERT INTO whatsapp_timesheet_inbox (
        sender_name,
        sender_phone,
        message_text,
        media_filename,
        media_path,
        parse_source,
        source_channel,
        status,
        matched_relation_id,
        matched_candidate_name,
        employee_name,
        principal_name,
        project_name,
        work_date,
        hours,
        break_minutes,
        selected_principal_id,
        selected_project_id,
        validated_at,
        parsed_fields,
        overall_confidence,
        received_at,
        created_at,
        updated_at
    )
    SELECT employee_name,
           sender_phone,
           'Test urenbriefje volledig loonjaar 2026 P' || LPAD(period_number::text, 2, '0') || ' WK' || week_number,
           'test-payroll-year-2026-p' || LPAD(period_number::text, 2, '0') || '-wk' || week_number || '-relation-' || relation_id || '.jpg',
           '',
           'testdata_full_year',
           'testdata',
           'loon_te_berekenen',
           relation_id,
           employee_name,
           employee_name,
           principal_name,
           project_name,
           work_date,
           hours,
           0,
           principal_id,
           project_id,
           NOW(),
           jsonb_build_object(
               'employee_name', jsonb_build_object('value', employee_name, 'confidence', 98),
               'week_number', jsonb_build_object('value', week_number::text, 'confidence', 98),
               'total_hours', jsonb_build_object('value', hours::text, 'confidence', 98),
               'total_hours_check', jsonb_build_object('value', 'klopt', 'confidence', 98),
               'principal_name', jsonb_build_object('value', principal_name, 'confidence', 95),
               'project_name', jsonb_build_object('value', project_name, 'confidence', 95),
               'payroll_period', jsonb_build_object('value', period_number::text, 'confidence', 98)
           ),
           98,
           (
               work_date::timestamp
               + ((8 + (candidate_index % 8)) * INTERVAL '1 hour')
               + (((candidate_index * 7 + period_number) % 60) * INTERVAL '1 minute')
           ),
           NOW(),
           NOW()
    FROM timesheet_seed s
    WHERE NOT EXISTS (
        SELECT 1
        FROM whatsapp_timesheet_inbox existing
        WHERE existing.media_filename = 'test-payroll-year-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
    )
    RETURNING id
)
INSERT INTO project_time_bookings (
    timesheet_inbox_id,
    relation_id,
    principal_id,
    project_id,
    payroll_cao_setting_id,
    payroll_period_id,
    work_date,
    hours,
    status,
    created_at,
    updated_at
)
SELECT w.id,
       s.relation_id,
       s.principal_id,
       s.project_id,
       s.payroll_cao_setting_id,
       s.payroll_period_id,
       s.work_date,
       s.hours,
       'loon_te_berekenen',
       NOW(),
       NOW()
FROM whatsapp_timesheet_inbox w
JOIN timesheet_seed s
    ON w.media_filename = 'test-payroll-year-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
WHERE NOT EXISTS (
    SELECT 1
    FROM project_time_bookings existing
    WHERE existing.timesheet_inbox_id = w.id
);

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
    'Volledig testjaar loonperiodes gevuld',
    'payroll_datamodel',
    'Testjaar 2026',
    'Ontbrekende loonperiodes en testuren voor het volledige loonjaar 2026 toegevoegd zonder bestaande workflowstatussen te overschrijven.',
    'Systeem',
    jsonb_build_object(
        'year', 2026,
        'periods_per_year', 13,
        'source', 'migrations/039_full_year_test_payroll.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Volledig testjaar loonperiodes gevuld'
      AND entity_type = 'payroll_datamodel'
);
