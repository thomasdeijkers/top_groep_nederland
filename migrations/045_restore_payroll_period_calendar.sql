INSERT INTO payroll_years (year, status, notes, created_at, updated_at)
VALUES (2026, 'active', 'Loonjaar met 13 periodes van 4 weken.', NOW(), NOW())
ON CONFLICT (year)
DO UPDATE SET
    period_count = 13,
    weeks_per_period = 4,
    updated_at = NOW();

WITH missing_periods AS (
    SELECT n.period_number
    FROM generate_series(1, 13) AS n(period_number)
    WHERE NOT EXISTS (
        SELECT 1
        FROM payroll_periods p
        WHERE p.year = 2026
          AND p.period_number = n.period_number
    )
), anchor AS (
    SELECT DATE '2026-01-05' AS first_start_date
)
INSERT INTO payroll_periods (
    payroll_year_id,
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
SELECT y.id,
       2026,
       m.period_number,
       'Periode ' || LPAD(m.period_number::text, 2, '0') || ' 2026',
       (a.first_start_date + ((m.period_number - 1) * 28) * INTERVAL '1 day')::date,
       (a.first_start_date + (((m.period_number - 1) * 28) + 27) * INTERVAL '1 day')::date,
       'open',
       'Herstelde loonperiodekalender; urenbriefjes en verwerking blijven leeg.',
       NOW(),
       NOW()
FROM missing_periods m
CROSS JOIN anchor a
JOIN payroll_years y ON y.year = 2026
ON CONFLICT (year, period_number)
DO NOTHING;

UPDATE payroll_periods p
SET payroll_year_id = y.id,
    updated_at = NOW()
FROM payroll_years y
WHERE p.year = y.year
  AND p.payroll_year_id IS NULL;

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
    source_channel,
    created_at
)
SELECT
    'Deploy',
    'Loonperiodekalender hersteld',
    'payroll_period_calendar',
    'Loonjaar 2026',
    'De loonperiodes en weken zijn beschikbaar zonder urenbriefjes of loonverwerking te vullen.',
    'Systeem',
    jsonb_build_object('source_channel', 'restore_period_calendar_045', 'year', 2026),
    'restore_period_calendar_045',
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE entity_type = 'payroll_period_calendar'
      AND metadata->>'source_channel' = 'restore_period_calendar_045'
);
