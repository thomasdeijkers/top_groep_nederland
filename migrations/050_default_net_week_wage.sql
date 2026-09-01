-- Tijdelijke basisafspraak: alle kandidaten krijgen een fictief netto weekloon bij 40 uur.
-- De loonperiode rekent vervolgens pro rata: netto weekloon / 40 * gewerkte uren.

UPDATE payroll_employee_arrangements
SET net_base_40h = 750,
    net_reference_week = 750,
    updated_at = NOW()
WHERE COALESCE(status, 'concept') <> 'archief';

INSERT INTO payroll_employee_arrangements (
    relation_id,
    valid_from_year,
    valid_from_period_number,
    cao_branch,
    contract_hours_4w,
    net_base_40h,
    net_reference_week,
    status,
    source,
    notes,
    created_at,
    updated_at
)
SELECT r.id,
       2026,
       1,
       'bouwplaats',
       40,
       750,
       750,
       'concept',
       'default_net_week_wage',
       'Fictieve netto weekloonafspraak van EUR 750 voor test/verloningsbasis.',
       NOW(),
       NOW()
FROM relations r
WHERE r.relation_type = 'candidate'
  AND r.archived_at IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM payroll_employee_arrangements a
      WHERE a.relation_id = r.id
        AND COALESCE(a.status, 'concept') <> 'archief'
  )
ON CONFLICT (relation_id, valid_from_year, valid_from_period_number)
DO UPDATE SET
    net_base_40h = 750,
    net_reference_week = 750,
    updated_at = NOW();

UPDATE payroll_week_inputs i
SET arrangement_id = a.id,
    updated_at = NOW()
FROM payroll_employee_arrangements a,
     payroll_periods p
WHERE p.id = i.payroll_period_id
  AND a.relation_id = i.relation_id
  AND COALESCE(a.status, 'concept') <> 'archief'
  AND LOWER(COALESCE(p.status, '')) <> 'archief'
  AND (
      a.valid_from_year < p.year
      OR (a.valid_from_year = p.year AND a.valid_from_period_number <= p.period_number)
  )
  AND a.id = (
      SELECT a2.id
      FROM payroll_employee_arrangements a2
      WHERE a2.relation_id = i.relation_id
        AND COALESCE(a2.status, 'concept') <> 'archief'
        AND (
            a2.valid_from_year < p.year
            OR (a2.valid_from_year = p.year AND a2.valid_from_period_number <= p.period_number)
        )
      ORDER BY a2.valid_from_year DESC, a2.valid_from_period_number DESC, a2.id DESC
      LIMIT 1
  );

UPDATE payroll_week_results r
SET arrangement_id = COALESCE(r.arrangement_id, i.arrangement_id),
    relation_id = COALESCE(r.relation_id, i.relation_id),
    net_wage_amount = ROUND(750 * COALESCE(
        NULLIF(r.worked_hours + r.vacation_hours + r.sickness_hours + r.rv_hours + r.kv_hours + r.holiday_hours, 0),
        r.worked_hours,
        0
    ) / 40, 2),
    net_week_total = ROUND(750 * COALESCE(
        NULLIF(r.worked_hours + r.vacation_hours + r.sickness_hours + r.rv_hours + r.kv_hours + r.holiday_hours, 0),
        r.worked_hours,
        0
    ) / 40, 2) + COALESCE(r.travel_amount, 0) + COALESCE(r.day_allowance_amount, 0) + COALESCE(r.extra_net_amount, 0),
    calculation_status = CASE
        WHEN COALESCE(r.arrangement_id, i.arrangement_id) IS NULL THEN 'mist_inrichting'
        ELSE 'concept'
    END,
    calculation_details = COALESCE(r.calculation_details, '{}'::jsonb) || jsonb_build_object(
        'formula', 'netto weekloonafspraak 40 uur / 40 * uren + reiskosten + dagvergoedingen',
        'net_base_40h', 750,
        'source', 'default_net_week_wage_migration'
    ),
    calculated_at = NOW(),
    updated_at = NOW()
FROM payroll_week_inputs i,
     payroll_periods p
WHERE i.id = r.payroll_week_input_id
  AND p.id = r.payroll_period_id
  AND LOWER(COALESCE(p.status, '')) <> 'archief';
