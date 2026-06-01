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
    5,
    'Periode 5 - 2026',
    DATE '2026-05-04',
    DATE '2026-05-31',
    'open',
    'Demo vierwekelijkse bouwperiode',
    NOW(),
    NOW()
)
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
SELECT p.id, week_data.week_index, week_data.week_number, week_data.start_date, week_data.end_date, NOW(), NOW()
FROM payroll_periods p
CROSS JOIN (
    VALUES
        (1, 19, DATE '2026-05-04', DATE '2026-05-10'),
        (2, 20, DATE '2026-05-11', DATE '2026-05-17'),
        (3, 21, DATE '2026-05-18', DATE '2026-05-24'),
        (4, 22, DATE '2026-05-25', DATE '2026-05-31')
) AS week_data(week_index, week_number, start_date, end_date)
WHERE p.year = 2026
  AND p.period_number = 5
ON CONFLICT (payroll_period_id, week_index)
DO NOTHING;

UPDATE project_time_bookings b
SET payroll_period_id = p.id,
    updated_at = NOW()
FROM payroll_periods p
WHERE p.year = 2026
  AND p.period_number = 5
  AND b.work_date BETWEEN p.start_date AND p.end_date
  AND b.payroll_period_id IS NULL;
