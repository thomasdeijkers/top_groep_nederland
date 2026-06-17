CREATE TABLE IF NOT EXISTS payroll_period_settlements (
    id SERIAL PRIMARY KEY,
    payroll_period_id INTEGER NOT NULL REFERENCES payroll_periods(id) ON DELETE CASCADE,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    arrangement_id INTEGER REFERENCES payroll_employee_arrangements(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    week_count INTEGER NOT NULL DEFAULT 0,
    total_worked_days NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_vacation_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_sickness_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_rv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_kv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_holiday_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    net_wage_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    travel_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    day_allowance_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    extra_net_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    advance_weeks_1_3 NUMERIC(12,2) NOT NULL DEFAULT 0,
    week_4_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_period_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    payment_schedule TEXT NOT NULL DEFAULT 'weekly',
    settlement_status TEXT NOT NULL DEFAULT 'concept',
    status_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_period_id, employee_name)
);

CREATE INDEX IF NOT EXISTS idx_payroll_period_settlements_period
    ON payroll_period_settlements (payroll_period_id, settlement_status);

CREATE INDEX IF NOT EXISTS idx_payroll_period_settlements_relation
    ON payroll_period_settlements (relation_id, calculated_at DESC);

WITH settlement_source AS (
    SELECT r.payroll_period_id,
           MAX(r.relation_id) AS relation_id,
           MAX(r.arrangement_id) AS arrangement_id,
           r.employee_name,
           COUNT(*) AS week_count,
           COALESCE(SUM(r.worked_days), 0) AS total_worked_days,
           COALESCE(SUM(r.worked_hours), 0) AS total_worked_hours,
           COALESCE(SUM(r.vacation_hours), 0) AS total_vacation_hours,
           COALESCE(SUM(r.sickness_hours), 0) AS total_sickness_hours,
           COALESCE(SUM(r.rv_hours), 0) AS total_rv_hours,
           COALESCE(SUM(r.kv_hours), 0) AS total_kv_hours,
           COALESCE(SUM(r.holiday_hours), 0) AS total_holiday_hours,
           COALESCE(SUM(r.total_km), 0) AS total_km,
           COALESCE(SUM(r.net_wage_amount), 0) AS net_wage_amount,
           COALESCE(SUM(r.travel_amount), 0) AS travel_amount,
           COALESCE(SUM(r.day_allowance_amount), 0) AS day_allowance_amount,
           COALESCE(SUM(r.extra_net_amount), 0) AS extra_net_amount,
           COALESCE(SUM(r.net_week_total) FILTER (WHERE w.week_index BETWEEN 1 AND 3), 0) AS advance_weeks_1_3,
           COALESCE(SUM(r.net_week_total) FILTER (WHERE w.week_index = 4), 0) AS week_4_amount,
           COALESCE(SUM(r.net_week_total), 0) AS total_period_amount,
           COALESCE(MAX(a.payment_schedule), 'weekly') AS payment_schedule,
           COUNT(*) FILTER (WHERE r.calculation_status = 'mist_inrichting') AS missing_arrangement_count,
           COUNT(*) FILTER (WHERE r.calculation_status = 'mist_netto_basisloon') AS missing_wage_count,
           COUNT(*) FILTER (WHERE r.calculation_status = 'concept') AS concept_count,
           STRING_AGG(DISTINCT r.calculation_status, ', ' ORDER BY r.calculation_status) AS calculation_statuses
    FROM payroll_week_results r
    LEFT JOIN payroll_period_weeks w ON w.id = r.payroll_period_week_id
    LEFT JOIN payroll_employee_arrangements a ON a.id = r.arrangement_id
    GROUP BY r.payroll_period_id, r.employee_name
)
INSERT INTO payroll_period_settlements (
    payroll_period_id,
    relation_id,
    arrangement_id,
    employee_name,
    week_count,
    total_worked_days,
    total_worked_hours,
    total_vacation_hours,
    total_sickness_hours,
    total_rv_hours,
    total_kv_hours,
    total_holiday_hours,
    total_km,
    net_wage_amount,
    travel_amount,
    day_allowance_amount,
    extra_net_amount,
    advance_weeks_1_3,
    week_4_amount,
    total_period_amount,
    payment_schedule,
    settlement_status,
    status_details,
    calculated_at,
    created_at,
    updated_at
)
SELECT payroll_period_id,
       relation_id,
       arrangement_id,
       employee_name,
       week_count,
       total_worked_days,
       total_worked_hours,
       total_vacation_hours,
       total_sickness_hours,
       total_rv_hours,
       total_kv_hours,
       total_holiday_hours,
       total_km,
       net_wage_amount,
       travel_amount,
       day_allowance_amount,
       extra_net_amount,
       advance_weeks_1_3,
       CASE
           WHEN payment_schedule = 'four_weekly' THEN total_period_amount
           ELSE week_4_amount
       END AS week_4_amount,
       total_period_amount,
       payment_schedule,
       CASE
           WHEN missing_arrangement_count > 0 THEN 'mist_inrichting'
           WHEN missing_wage_count > 0 THEN 'mist_netto_basisloon'
           WHEN concept_count > 0 THEN 'concept'
           ELSE 'controle'
       END AS settlement_status,
       jsonb_build_object(
           'calculation_statuses', calculation_statuses,
           'missing_arrangement_count', missing_arrangement_count,
           'missing_wage_count', missing_wage_count,
           'concept_count', concept_count,
           'source', 'payroll_week_results'
       ),
       NOW(),
       NOW(),
       NOW()
FROM settlement_source
ON CONFLICT (payroll_period_id, employee_name)
DO UPDATE SET
    relation_id = EXCLUDED.relation_id,
    arrangement_id = EXCLUDED.arrangement_id,
    week_count = EXCLUDED.week_count,
    total_worked_days = EXCLUDED.total_worked_days,
    total_worked_hours = EXCLUDED.total_worked_hours,
    total_vacation_hours = EXCLUDED.total_vacation_hours,
    total_sickness_hours = EXCLUDED.total_sickness_hours,
    total_rv_hours = EXCLUDED.total_rv_hours,
    total_kv_hours = EXCLUDED.total_kv_hours,
    total_holiday_hours = EXCLUDED.total_holiday_hours,
    total_km = EXCLUDED.total_km,
    net_wage_amount = EXCLUDED.net_wage_amount,
    travel_amount = EXCLUDED.travel_amount,
    day_allowance_amount = EXCLUDED.day_allowance_amount,
    extra_net_amount = EXCLUDED.extra_net_amount,
    advance_weeks_1_3 = EXCLUDED.advance_weeks_1_3,
    week_4_amount = EXCLUDED.week_4_amount,
    total_period_amount = EXCLUDED.total_period_amount,
    payment_schedule = EXCLUDED.payment_schedule,
    settlement_status = EXCLUDED.settlement_status,
    status_details = EXCLUDED.status_details,
    calculated_at = NOW(),
    updated_at = NOW();
