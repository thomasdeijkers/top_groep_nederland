WITH fallback_candidate AS (
    INSERT INTO relations (
        relation_type,
        external_id,
        name,
        phone,
        status,
        source,
        raw_data,
        created_at,
        updated_at
    )
    SELECT 'candidate',
           'demo-payroll-candidate-001',
           'Demo Payroll Medewerker',
           '+31 6 0000 0001',
           'Actief',
           'testdata_full_period',
           jsonb_build_object('seed', 'migrations/040_one_period_test_hours.sql'),
           NOW(),
           NOW()
    WHERE NOT EXISTS (
        SELECT 1
        FROM relations
        WHERE relation_type = 'candidate'
          AND archived_at IS NULL
          AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'verwijderd')
    )
    ON CONFLICT DO NOTHING
    RETURNING id
), selected_period AS (
    SELECT id, year, period_number, start_date, end_date
    FROM payroll_periods
    WHERE year = 2026
    ORDER BY period_number ASC, id ASC
    LIMIT 1
), candidate_source AS (
    SELECT id,
           name,
           phone
    FROM relations
    WHERE relation_type = 'candidate'
      AND archived_at IS NULL
      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'verwijderd')
    UNION ALL
    SELECT r.id,
           r.name,
           r.phone
    FROM fallback_candidate f
    JOIN relations r ON r.id = f.id
), candidate_seed AS (
    SELECT id,
           name,
           phone,
           ROW_NUMBER() OVER (ORDER BY name, id) AS candidate_index
    FROM candidate_source
    ORDER BY name, id
    LIMIT 8
), week_seed AS (
    SELECT w.id AS payroll_period_week_id,
           w.week_index,
           w.week_number,
           w.start_date
    FROM payroll_period_weeks w
    JOIN selected_period p ON p.id = w.payroll_period_id
), timesheet_seed AS (
    SELECT p.id AS payroll_period_id,
           p.period_number,
           w.payroll_period_week_id,
           w.week_index,
           w.week_number,
           c.id AS relation_id,
           c.name AS employee_name,
           COALESCE(NULLIF(c.phone, ''), '+31 6 0000 0000') AS sender_phone,
           c.candidate_index,
           (w.start_date + ((c.candidate_index - 1) % 5) * INTERVAL '1 day')::date AS work_date,
           (32 + ((c.candidate_index + w.week_index + p.period_number) % 5))::numeric AS hours
    FROM selected_period p
    JOIN week_seed w ON TRUE
    CROSS JOIN candidate_seed c
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
           'Fictief urenbriefje loonperiode ' || LPAD(period_number::text, 2, '0') || ' WK' || week_number,
           'test-one-period-2026-p' || LPAD(period_number::text, 2, '0') || '-wk' || week_number || '-relation-' || relation_id || '.jpg',
           '',
           'testdata_one_period',
           'testdata',
           'loon_te_berekenen',
           relation_id,
           employee_name,
           employee_name,
           'Fictieve opdrachtgever',
           'Fictief testproject',
           work_date,
           hours,
           0,
           NULL,
           NULL,
           NOW(),
           jsonb_build_object(
               'employee_name', jsonb_build_object('value', employee_name, 'confidence', 98),
               'week_number', jsonb_build_object('value', week_number::text, 'confidence', 98),
               'total_hours', jsonb_build_object('value', hours::text, 'confidence', 98),
               'total_hours_check', jsonb_build_object('value', 'klopt', 'confidence', 98),
               'principal_name', jsonb_build_object('value', 'Fictieve opdrachtgever', 'confidence', 95),
               'project_name', jsonb_build_object('value', 'Fictief testproject', 'confidence', 95),
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
        WHERE existing.media_filename = 'test-one-period-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
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
       NULL,
       NULL,
       NULL,
       s.payroll_period_id,
       s.work_date,
       s.hours,
       'loon_te_berekenen',
       NOW(),
       NOW()
FROM whatsapp_timesheet_inbox w
JOIN timesheet_seed s
    ON w.media_filename = 'test-one-period-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
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
    'Een loonperiode met fictieve uren gevuld',
    'payroll_datamodel',
    'Fictieve loonperiode',
    'Een bestaande loonperiode gevuld met fictieve urenbriefjes voor bestaande kandidaten, direct klaar voor loonberekening.',
    'Systeem',
    jsonb_build_object(
        'year', 2026,
        'source', 'migrations/040_one_period_test_hours.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Een loonperiode met fictieve uren gevuld'
      AND entity_type = 'payroll_datamodel'
);
