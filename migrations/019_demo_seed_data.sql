INSERT INTO payroll_cao_settings (
    name,
    version_label,
    effective_from,
    effective_until,
    standard_week_hours,
    overtime_after_hours,
    weekday_overtime_percent,
    saturday_percent,
    sunday_percent,
    holiday_percent,
    travel_cost_per_km,
    default_hourly_wage,
    status,
    source,
    notes,
    created_at,
    updated_at
)
SELECT *
FROM (
    VALUES
        ('Bouw & Infra', 'Demo 2026', DATE '2026-01-01', DATE '2026-12-31', 40, 40, 125, 150, 200, 200, 0.23, 21.50, 'actief', 'demo', 'Demo CAO voor bouwplaatsmedewerkers', NOW(), NOW()),
        ('UTA', 'Demo 2026', DATE '2026-01-01', DATE '2026-12-31', 40, 40, 125, 150, 200, 200, 0.23, 24.75, 'actief', 'demo', 'Demo CAO voor UTA functies', NOW(), NOW()),
        ('SAVG', 'Demo 2026', DATE '2026-01-01', DATE '2026-12-31', 37.5, 37.5, 125, 150, 200, 200, 0.23, 20.25, 'actief', 'demo', 'Demo CAO voor schilders/afbouw', NOW(), NOW())
) AS demo(
    name,
    version_label,
    effective_from,
    effective_until,
    standard_week_hours,
    overtime_after_hours,
    weekday_overtime_percent,
    saturday_percent,
    sunday_percent,
    holiday_percent,
    travel_cost_per_km,
    default_hourly_wage,
    status,
    source,
    notes,
    created_at,
    updated_at
)
WHERE NOT EXISTS (
    SELECT 1
    FROM payroll_cao_settings existing
    WHERE existing.name = demo.name
      AND existing.version_label = demo.version_label
      AND existing.source = 'demo'
);

INSERT INTO relations (
    relation_type,
    external_id,
    name,
    first_name,
    last_name,
    email,
    phone,
    address,
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
    ('candidate', 'demo-candidate-ruben-hellemons', 'Ruben Hellemons', 'Ruben', 'Hellemons', 'ruben.demo@example.nl', '+31 6 1000 0001', 'Havenstraat 12', '3011 AA', 'Rotterdam', 'Nederland', 'Beschikbaar', 'demo', 'Planning', 'Per direct', '21.50', 'Demo kandidaat - bouwplaatsmedewerker', '{"demo": true, "skill": "Onderhoud en timmerwerk"}'::jsonb, NOW(), NOW()),
    ('candidate', 'demo-candidate-andre-sintenie', 'Andre Sintenie', 'Andre', 'Sintenie', 'andre.demo@example.nl', '+31 6 1000 0002', 'Stationsweg 8', '2515 BN', 'Den Haag', 'Nederland', 'Actief', 'demo', 'Planning', 'Ingepland', '20.25', 'Demo kandidaat - SAVG', '{"demo": true, "skill": "Schilderwerk"}'::jsonb, NOW(), NOW()),
    ('candidate', 'demo-candidate-dennis-aarts', 'Dennis Aarts', 'Dennis', 'Aarts', 'dennis.demo@example.nl', '+31 6 1000 0003', 'Bouwweg 4', '3511 ZZ', 'Utrecht', 'Nederland', 'Actief', 'demo', 'Planning', 'Ingepland', '24.75', 'Demo kandidaat - UTA', '{"demo": true, "skill": "Assistent uitvoerder"}'::jsonb, NOW(), NOW()),
    ('candidate', 'demo-candidate-frank-stouthart', 'Frank Stouthart', 'Frank', 'Stouthart', 'frank.demo@example.nl', '+31 6 1000 0004', 'Lijnbaan 22', '4811 KL', 'Breda', 'Nederland', 'Beschikbaar', 'demo', 'Planning', 'Binnen 1 week', '22.10', 'Demo kandidaat - bouw', '{"demo": true, "skill": "Allround bouw"}'::jsonb, NOW(), NOW())
ON CONFLICT (relation_type, external_id)
WHERE external_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    address = EXCLUDED.address,
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
    updated_at = NOW();

INSERT INTO relations (
    relation_type,
    external_id,
    name,
    contact_name,
    email,
    phone,
    website,
    address,
    postal_code,
    city,
    country,
    status,
    source,
    kvk_number,
    vat_number,
    notes,
    raw_data,
    created_at,
    updated_at
)
VALUES
    ('principal', 'demo-principal-olympus-bouw', 'Olympus Bouw B.V.', 'Sander de Vries', 'planning@olympusbouw.example', '+31 10 100 2000', 'https://olympusbouw.example', 'Aannemersplein 1', '3012 AB', 'Rotterdam', 'Nederland', 'Actief', 'demo', '12345678', 'NL001234567B01', 'Demo opdrachtgever voor bouwprojecten', '{"demo": true, "sector": "Bouw"}'::jsonb, NOW(), NOW()),
    ('principal', 'demo-principal-vliet-afbouw', 'Van Vliet Afbouw', 'Marieke Jansen', 'uren@vlietafbouw.example', '+31 70 200 3000', 'https://vlietafbouw.example', 'Industrieweg 18', '2491 CD', 'Den Haag', 'Nederland', 'Actief', 'demo', '87654321', 'NL009876543B01', 'Demo opdrachtgever voor SAVG werkzaamheden', '{"demo": true, "sector": "Afbouw"}'::jsonb, NOW(), NOW()),
    ('principal', 'demo-principal-rijnstad-projecten', 'Rijnstad Projecten', 'Koen Brouwer', 'projecten@rijnstad.example', '+31 30 300 4000', 'https://rijnstad.example', 'Kanaalweg 40', '3526 KM', 'Utrecht', 'Nederland', 'Actief', 'demo', '24681357', 'NL002468135B01', 'Demo opdrachtgever voor UTA/projectleiding', '{"demo": true, "sector": "Projectontwikkeling"}'::jsonb, NOW(), NOW())
ON CONFLICT (relation_type, external_id)
WHERE external_id IS NOT NULL
DO UPDATE SET
    name = EXCLUDED.name,
    contact_name = EXCLUDED.contact_name,
    email = EXCLUDED.email,
    phone = EXCLUDED.phone,
    website = EXCLUDED.website,
    address = EXCLUDED.address,
    postal_code = EXCLUDED.postal_code,
    city = EXCLUDED.city,
    country = EXCLUDED.country,
    status = EXCLUDED.status,
    source = EXCLUDED.source,
    kvk_number = EXCLUDED.kvk_number,
    vat_number = EXCLUDED.vat_number,
    notes = EXCLUDED.notes,
    raw_data = EXCLUDED.raw_data,
    updated_at = NOW();

INSERT INTO vacancies (
    external_id,
    title,
    reference_number,
    status,
    owner,
    relation_name,
    location,
    publication_status,
    website_enabled,
    indeed_enabled,
    applicant_count,
    payroll_cao_setting_id,
    raw_data,
    created_at,
    updated_at
)
VALUES
    ('demo-project-rotterdam-centrum', 'Renovatie Rotterdam Centrum', 'P-DEMO-001', 'Actief', 'Planning', 'Olympus Bouw B.V.', 'Rotterdam', 'project', FALSE, FALSE, 0, (SELECT id FROM payroll_cao_settings WHERE name = 'Bouw & Infra' AND source = 'demo' ORDER BY id DESC LIMIT 1), '{"demo": true, "record_type": "project", "notes": "Demo project met bouw CAO"}'::jsonb, NOW(), NOW()),
    ('demo-project-den-haag-afbouw', 'Afbouw Den Haag Zuid', 'P-DEMO-002', 'Actief', 'Planning', 'Van Vliet Afbouw', 'Den Haag', 'project', FALSE, FALSE, 0, (SELECT id FROM payroll_cao_settings WHERE name = 'SAVG' AND source = 'demo' ORDER BY id DESC LIMIT 1), '{"demo": true, "record_type": "project", "notes": "Demo project met SAVG CAO"}'::jsonb, NOW(), NOW()),
    ('demo-project-utrecht-uta', 'Uitvoerder Utrecht Oost', 'P-DEMO-003', 'Voorbereiding', 'Planning', 'Rijnstad Projecten', 'Utrecht', 'project', FALSE, FALSE, 0, (SELECT id FROM payroll_cao_settings WHERE name = 'UTA' AND source = 'demo' ORDER BY id DESC LIMIT 1), '{"demo": true, "record_type": "project", "notes": "Demo project met UTA CAO"}'::jsonb, NOW(), NOW())
ON CONFLICT (external_id)
DO UPDATE SET
    title = EXCLUDED.title,
    reference_number = EXCLUDED.reference_number,
    status = EXCLUDED.status,
    owner = EXCLUDED.owner,
    relation_name = EXCLUDED.relation_name,
    location = EXCLUDED.location,
    publication_status = EXCLUDED.publication_status,
    payroll_cao_setting_id = EXCLUDED.payroll_cao_setting_id,
    raw_data = EXCLUDED.raw_data,
    updated_at = NOW();

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
SELECT *
FROM (
    SELECT
        'Demo upload' AS sender_name,
        '+31 6 1000 0001' AS sender_phone,
        'Demo urenbriefje: Ruben Hellemons - Renovatie Rotterdam Centrum' AS message_text,
        'demo-timesheet-ruben-rotterdam-wk20.jpg' AS media_filename,
        '' AS media_path,
        'demo' AS parse_source,
        'manual_upload' AS source_channel,
        'loon_te_berekenen' AS status,
        (SELECT id FROM relations WHERE external_id = 'demo-candidate-ruben-hellemons' AND relation_type = 'candidate') AS matched_relation_id,
        'Ruben Hellemons' AS matched_candidate_name,
        'Ruben Hellemons' AS employee_name,
        'Olympus Bouw B.V.' AS principal_name,
        'Renovatie Rotterdam Centrum' AS project_name,
        DATE '2026-05-18' AS work_date,
        40.00 AS hours,
        0 AS break_minutes,
        (SELECT id FROM relations WHERE external_id = 'demo-principal-olympus-bouw' AND relation_type = 'principal') AS selected_principal_id,
        (SELECT id FROM vacancies WHERE external_id = 'demo-project-rotterdam-centrum') AS selected_project_id,
        NOW() AS validated_at,
        '{"employee_name": {"value": "Ruben Hellemons", "confidence": 98}, "total_hours": {"value": "40", "confidence": 98}, "total_hours_check": {"value": "demo", "confidence": 98}}'::jsonb AS parsed_fields,
        98 AS overall_confidence,
        NOW() AS received_at,
        NOW() AS created_at,
        NOW() AS updated_at
    UNION ALL
    SELECT
        'Demo upload',
        '+31 6 1000 0002',
        'Demo urenbriefje: Andre Sintenie - Afbouw Den Haag Zuid',
        'demo-timesheet-andre-den-haag-wk20.jpg',
        '',
        'demo',
        'manual_upload',
        'loon_te_berekenen',
        (SELECT id FROM relations WHERE external_id = 'demo-candidate-andre-sintenie' AND relation_type = 'candidate'),
        'Andre Sintenie',
        'Andre Sintenie',
        'Van Vliet Afbouw',
        'Afbouw Den Haag Zuid',
        DATE '2026-05-19',
        37.50,
        0,
        (SELECT id FROM relations WHERE external_id = 'demo-principal-vliet-afbouw' AND relation_type = 'principal'),
        (SELECT id FROM vacancies WHERE external_id = 'demo-project-den-haag-afbouw'),
        NOW(),
        '{"employee_name": {"value": "Andre Sintenie", "confidence": 98}, "total_hours": {"value": "37.5", "confidence": 98}, "total_hours_check": {"value": "demo", "confidence": 98}}'::jsonb,
        98,
        NOW(),
        NOW(),
        NOW()
    UNION ALL
    SELECT
        'Demo upload',
        '+31 6 1000 0003',
        'Demo urenbriefje: Dennis Aarts - Uitvoerder Utrecht Oost',
        'demo-timesheet-dennis-utrecht-wk20.jpg',
        '',
        'demo',
        'manual_upload',
        'loon_te_berekenen',
        (SELECT id FROM relations WHERE external_id = 'demo-candidate-dennis-aarts' AND relation_type = 'candidate'),
        'Dennis Aarts',
        'Dennis Aarts',
        'Rijnstad Projecten',
        'Uitvoerder Utrecht Oost',
        DATE '2026-05-20',
        32.00,
        0,
        (SELECT id FROM relations WHERE external_id = 'demo-principal-rijnstad-projecten' AND relation_type = 'principal'),
        (SELECT id FROM vacancies WHERE external_id = 'demo-project-utrecht-uta'),
        NOW(),
        '{"employee_name": {"value": "Dennis Aarts", "confidence": 98}, "total_hours": {"value": "32", "confidence": 98}, "total_hours_check": {"value": "demo", "confidence": 98}}'::jsonb,
        98,
        NOW(),
        NOW(),
        NOW()
) AS demo_timesheets
WHERE NOT EXISTS (
    SELECT 1
    FROM whatsapp_timesheet_inbox existing
    WHERE existing.media_filename = demo_timesheets.media_filename
);

INSERT INTO project_time_bookings (
    timesheet_inbox_id,
    relation_id,
    principal_id,
    project_id,
    payroll_cao_setting_id,
    work_date,
    hours,
    status,
    created_at,
    updated_at
)
SELECT
    w.id,
    w.matched_relation_id,
    w.selected_principal_id,
    w.selected_project_id,
    v.payroll_cao_setting_id,
    w.work_date,
    w.hours,
    'loon_te_berekenen',
    NOW(),
    NOW()
FROM whatsapp_timesheet_inbox w
JOIN vacancies v
    ON v.id = w.selected_project_id
WHERE w.media_filename IN (
    'demo-timesheet-ruben-rotterdam-wk20.jpg',
    'demo-timesheet-andre-den-haag-wk20.jpg',
    'demo-timesheet-dennis-utrecht-wk20.jpg'
)
  AND NOT EXISTS (
      SELECT 1
      FROM project_time_bookings existing
      WHERE existing.timesheet_inbox_id = w.id
  );
