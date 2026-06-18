INSERT INTO relations (
    relation_type,
    external_id,
    name,
    first_name,
    last_name,
    contact_name,
    email,
    phone,
    address,
    street,
    house_number,
    postal_code,
    city,
    country,
    status,
    source,
    owner,
    availability,
    hourly_rate,
    notes,
    raw_data,
    created_at,
    updated_at
)
VALUES
    ('candidate', 'dashboard-demo-candidate-001', 'A Kursun', 'A', 'Kursun', NULL, 'a.kursun.demo@example.nl', '+31 6 0000 0001', 'Teststraat 1', 'Teststraat', '1', '3011 AA', 'Rotterdam', 'Nederland', 'Actief', 'dashboard_demo', 'Planning', 'Ingepland', '21.50', 'Dashboard demo kandidaat voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW()),
    ('candidate', 'dashboard-demo-candidate-002', 'A Spreng', 'A', 'Spreng', NULL, 'a.spreng.demo@example.nl', '+31 6 0000 0002', 'Teststraat 2', 'Teststraat', '2', '2515 BN', 'Den Haag', 'Nederland', 'Actief', 'dashboard_demo', 'Planning', 'Ingepland', '22.10', 'Dashboard demo kandidaat voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW()),
    ('candidate', 'dashboard-demo-candidate-003', 'A Bakker', 'A', 'Bakker', NULL, 'a.bakker.demo@example.nl', '+31 6 0000 0003', 'Teststraat 3', 'Teststraat', '3', '3511 ZZ', 'Utrecht', 'Nederland', 'Actief', 'dashboard_demo', 'Planning', 'Ingepland', '20.75', 'Dashboard demo kandidaat voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW()),
    ('candidate', 'dashboard-demo-candidate-004', 'A Lalta', 'A', 'Lalta', NULL, 'a.lalta.demo@example.nl', '+31 6 0000 0004', 'Teststraat 4', 'Teststraat', '4', '4811 KL', 'Breda', 'Nederland', 'Actief', 'dashboard_demo', 'Planning', 'Ingepland', '23.00', 'Dashboard demo kandidaat voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW()),
    ('principal', 'dashboard-demo-principal-001', 'TOP Demo Bouw B.V.', NULL, NULL, 'Planning Demo', 'planning.demo@example.nl', '+31 10 000 1000', 'Bouwplein 10', 'Bouwplein', '10', '3012 AB', 'Rotterdam', 'Nederland', 'Actief', 'dashboard_demo', NULL, NULL, NULL, 'Dashboard demo opdrachtgever voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW()),
    ('principal', 'dashboard-demo-principal-002', 'TOP Demo Afbouw B.V.', NULL, NULL, 'Administratie Demo', 'administratie.demo@example.nl', '+31 70 000 2000', 'Afbouwlaan 20', 'Afbouwlaan', '20', '2491 CD', 'Den Haag', 'Nederland', 'Actief', 'dashboard_demo', NULL, NULL, NULL, 'Dashboard demo opdrachtgever voor loonperiode-testdata', '{"demo": true, "seed": "041_dashboard_demo_payroll.sql"}'::jsonb, NOW(), NOW())
ON CONFLICT (relation_type, external_id)
WHERE external_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    contact_name = EXCLUDED.contact_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    address = EXCLUDED.address,
    street = EXCLUDED.street,
    house_number = EXCLUDED.house_number,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    owner = EXCLUDED.owner,
    availability = EXCLUDED.availability,
    hourly_rate = EXCLUDED.hourly_rate,
    notes = EXCLUDED.notes,
    raw_data = EXCLUDED.raw_data,
    archived_at = NULL,
    updated_at = NOW();

WITH selected_period AS (
    SELECT id, year, period_number, start_date, end_date
    FROM payroll_periods
    WHERE year = 2026
    ORDER BY period_number ASC, id ASC
    LIMIT 1
), candidate_seed AS (
    SELECT id,
           name,
           phone,
           ROW_NUMBER() OVER (ORDER BY CASE WHEN source = 'dashboard_demo' THEN 0 ELSE 1 END, name, id) AS candidate_index
    FROM relations
    WHERE relation_type = 'candidate'
      AND archived_at IS NULL
      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived', 'verwijderd')
    ORDER BY CASE WHEN source = 'dashboard_demo' THEN 0 ELSE 1 END, name, id
    LIMIT 8
), principal_seed AS (
    SELECT id, name
    FROM relations
    WHERE relation_type = 'principal'
      AND archived_at IS NULL
      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived', 'verwijderd')
    ORDER BY CASE WHEN source = 'dashboard_demo' THEN 0 ELSE 1 END, name, id
    LIMIT 1
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
           w.week_index,
           w.week_number,
           c.id AS relation_id,
           c.name AS employee_name,
           COALESCE(NULLIF(c.phone, ''), '+31 6 0000 0000') AS sender_phone,
           c.candidate_index,
           ps.id AS principal_id,
           ps.name AS principal_name,
           (w.start_date + ((c.candidate_index - 1) % 5) * INTERVAL '1 day')::date AS work_date,
           (32 + ((c.candidate_index + w.week_index + p.period_number) % 7))::numeric AS hours
    FROM selected_period p
    JOIN week_seed w ON TRUE
    CROSS JOIN candidate_seed c
    CROSS JOIN principal_seed ps
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
           'Dashboard demo urenbriefje periode ' || LPAD(period_number::text, 2, '0') || ' WK' || week_number,
           'dashboard-demo-2026-p' || LPAD(period_number::text, 2, '0') || '-wk' || week_number || '-relation-' || relation_id || '.jpg',
           '',
           'dashboard_demo_payroll',
           'testdata',
           'loon_te_berekenen',
           relation_id,
           employee_name,
           employee_name,
           principal_name,
           'Dashboard demo project',
           work_date,
           hours,
           0,
           principal_id,
           NULL,
           NOW(),
           jsonb_build_object(
               'employee_name', jsonb_build_object('value', employee_name, 'confidence', 98),
               'week_number', jsonb_build_object('value', week_number::text, 'confidence', 98),
               'total_hours', jsonb_build_object('value', hours::text, 'confidence', 98),
               'total_hours_check', jsonb_build_object('value', 'klopt', 'confidence', 98),
               'principal_name', jsonb_build_object('value', principal_name, 'confidence', 95),
               'project_name', jsonb_build_object('value', 'Dashboard demo project', 'confidence', 95),
               'payroll_period', jsonb_build_object('value', period_number::text, 'confidence', 98)
           ),
           98,
           (
               work_date::timestamp
               + ((8 + (candidate_index % 8)) * INTERVAL '1 hour')
               + (((candidate_index * 9 + period_number) % 60) * INTERVAL '1 minute')
           ),
           NOW(),
           NOW()
    FROM timesheet_seed s
    WHERE NOT EXISTS (
        SELECT 1
        FROM whatsapp_timesheet_inbox existing
        WHERE existing.media_filename = 'dashboard-demo-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
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
    ON w.media_filename = 'dashboard-demo-2026-p' || LPAD(s.period_number::text, 2, '0') || '-wk' || s.week_number || '-relation-' || s.relation_id || '.jpg'
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
    'Dashboard demo loonperiode gevuld',
    'payroll_datamodel',
    'Dashboard demo payroll',
    'Zichtbare demorelaties, een loonperiode en fictieve urenregels klaargezet voor controle van het dashboard.',
    'Systeem',
    jsonb_build_object(
        'year', 2026,
        'source', 'migrations/041_dashboard_demo_payroll.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Dashboard demo loonperiode gevuld'
      AND entity_type = 'payroll_datamodel'
);