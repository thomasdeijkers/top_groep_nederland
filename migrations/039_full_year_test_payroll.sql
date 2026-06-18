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
    'Volledig testjaar loonperiodes aangemaakt',
    'payroll_datamodel',
    'Testjaar 2026',
    'Ontbrekende loonperiodes en weken voor het volledige loonjaar 2026 toegevoegd.',
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
    WHERE action = 'Volledig testjaar loonperiodes aangemaakt'
      AND entity_type = 'payroll_datamodel'
);
