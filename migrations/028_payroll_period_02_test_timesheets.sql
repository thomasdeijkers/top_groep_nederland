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
VALUES (
    2026,
    2,
    'Periode 02 01/06 - 28/06',
    DATE '2026-06-01',
    DATE '2026-06-28',
    'open',
    'Testdata voor Excel-achtige verloningswerkmap WK23 t/m WK26.',
    NOW(),
    NOW()
)
ON CONFLICT (year, period_number)
DO UPDATE SET
    name = EXCLUDED.name,
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    status = EXCLUDED.status,
    notes = EXCLUDED.notes,
    updated_at = NOW();

INSERT INTO payroll_period_weeks (
    payroll_period_id,
    week_index,
    week_number,
    start_date,
    end_date,
    created_at,
    updated_at
)
SELECT p.id, week_data.week_index, week_data.week_number, week_data.start_date, week_data.end_date, NOW(), NOW()
FROM payroll_periods p
CROSS JOIN (
    VALUES
        (1, 23, DATE '2026-06-01', DATE '2026-06-07'),
        (2, 24, DATE '2026-06-08', DATE '2026-06-14'),
        (3, 25, DATE '2026-06-15', DATE '2026-06-21'),
        (4, 26, DATE '2026-06-22', DATE '2026-06-28')
) AS week_data(week_index, week_number, start_date, end_date)
WHERE p.year = 2026
  AND p.period_number = 2
ON CONFLICT (payroll_period_id, week_index)
DO UPDATE SET
    week_number = EXCLUDED.week_number,
    start_date = EXCLUDED.start_date,
    end_date = EXCLUDED.end_date,
    updated_at = NOW();

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
    LIMIT 15
),
default_principal AS (
    SELECT id, name
    FROM relations
    WHERE relation_type = 'principal'
      AND archived_at IS NULL
    ORDER BY id
    LIMIT 1
),
default_project AS (
    SELECT id, title, payroll_cao_setting_id
    FROM vacancies
    WHERE COALESCE(raw_data->>'record_type', 'vacancy') = 'project'
    ORDER BY id
    LIMIT 1
),
week_seed AS (
    SELECT *
    FROM (
        VALUES
            (1, 23, DATE '2026-06-01'),
            (2, 24, DATE '2026-06-08'),
            (3, 25, DATE '2026-06-15'),
            (4, 26, DATE '2026-06-22')
    ) AS week_data(week_index, week_number, week_start)
),
timesheet_seed AS (
    SELECT
        c.id AS relation_id,
        c.name AS employee_name,
        COALESCE(NULLIF(c.phone, ''), '+31 6 0000 0000') AS sender_phone,
        c.candidate_index,
        w.week_index,
        w.week_number,
        w.week_start + ((c.candidate_index - 1) % 5) * INTERVAL '1 day' AS work_date,
        (32 + ((c.candidate_index + w.week_index) % 4))::numeric AS hours,
        p.id AS principal_id,
        COALESCE(p.name, 'Test opdrachtgever') AS principal_name,
        v.id AS project_id,
        COALESCE(v.title, 'Test project') AS project_name,
        v.payroll_cao_setting_id,
        pp.id AS payroll_period_id
    FROM candidate_seed c
    CROSS JOIN week_seed w
    CROSS JOIN payroll_periods pp
    LEFT JOIN default_principal p ON TRUE
    LEFT JOIN default_project v ON TRUE
    WHERE pp.year = 2026
      AND pp.period_number = 2
),
inserted_timesheets AS (
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
    SELECT
        employee_name,
        sender_phone,
        'Test urenbriefje voor loonberekening periode 02 WK' || week_number,
        'test-period-02-wk' || week_number || '-relation-' || relation_id || '.jpg',
        '',
        'testdata',
        'testdata',
        'loon_te_berekenen',
        relation_id,
        employee_name,
        employee_name,
        principal_name,
        project_name,
        work_date::date,
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
            'project_name', jsonb_build_object('value', project_name, 'confidence', 95)
        ),
        98,
        NOW() - (week_index || ' days')::interval,
        NOW(),
        NOW()
    FROM timesheet_seed s
    WHERE NOT EXISTS (
        SELECT 1
        FROM whatsapp_timesheet_inbox existing
        WHERE existing.media_filename = 'test-period-02-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
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
SELECT
    w.id,
    s.relation_id,
    s.principal_id,
    s.project_id,
    s.payroll_cao_setting_id,
    s.payroll_period_id,
    s.work_date::date,
    s.hours,
    'loon_te_berekenen',
    NOW(),
    NOW()
FROM whatsapp_timesheet_inbox w
JOIN timesheet_seed s
    ON w.media_filename = 'test-period-02-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
WHERE NOT EXISTS (
    SELECT 1
    FROM project_time_bookings existing
    WHERE existing.timesheet_inbox_id = w.id
);
