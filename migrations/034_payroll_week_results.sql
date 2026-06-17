CREATE TABLE IF NOT EXISTS payroll_week_results (
    id SERIAL PRIMARY KEY,
    payroll_week_input_id INTEGER NOT NULL REFERENCES payroll_week_inputs(id) ON DELETE CASCADE,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE CASCADE,
    payroll_period_week_id INTEGER REFERENCES payroll_period_weeks(id) ON DELETE SET NULL,
    relation_id INTEGER REFERENCES relations(id) ON DELETE SET NULL,
    arrangement_id INTEGER REFERENCES payroll_employee_arrangements(id) ON DELETE SET NULL,
    employee_name TEXT NOT NULL,
    week_number INTEGER,
    worked_days NUMERIC(10,2) NOT NULL DEFAULT 0,
    worked_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    vacation_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    sickness_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    rv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    kv_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    holiday_hours NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_km NUMERIC(10,2) NOT NULL DEFAULT 0,
    net_wage_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    travel_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    day_allowance_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    extra_net_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_week_total NUMERIC(12,2) NOT NULL DEFAULT 0,
    travel_rate NUMERIC(10,4),
    calculation_status TEXT NOT NULL DEFAULT 'concept',
    calculation_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (payroll_week_input_id)
);

CREATE INDEX IF NOT EXISTS idx_payroll_week_results_period
    ON payroll_week_results (payroll_period_id, payroll_period_week_id, calculation_status);

CREATE INDEX IF NOT EXISTS idx_payroll_week_results_relation
    ON payroll_week_results (relation_id, calculated_at DESC);

WITH input_base AS (
    SELECT i.id AS payroll_week_input_id,
           i.payroll_period_id,
           i.payroll_period_week_id,
           i.relation_id,
           i.arrangement_id,
           i.employee_name,
           i.week_number,
           i.worked_hours,
           i.total_km,
           p.year,
           p.period_number,
           a.cao_branch,
           a.net_base_40h,
           a.vacation_rate_40h,
           a.sickness_rate_40h,
           a.holiday_rate_40h,
           a.company_car,
           a.own_transport_km_rate,
           COALESCE(day_totals.worked_days, 0) AS worked_days,
           COALESCE(day_totals.vacation_hours, 0) AS vacation_hours,
           COALESCE(day_totals.sickness_hours, 0) AS sickness_hours,
           COALESCE(day_totals.rv_hours, 0) AS rv_hours,
           COALESCE(day_totals.kv_hours, 0) AS kv_hours,
           COALESCE(day_totals.holiday_hours, 0) AS holiday_hours,
           COALESCE(allowance_totals.day_allowance_amount, 0) AS day_allowance_per_day
    FROM payroll_week_inputs i
    JOIN payroll_periods p ON p.id = i.payroll_period_id
    LEFT JOIN payroll_employee_arrangements a ON a.id = i.arrangement_id
    LEFT JOIN LATERAL (
        SELECT COUNT(*) FILTER (WHERE d.hours > 0) AS worked_days,
               SUM(CASE WHEN UPPER(COALESCE(d.day_code, '')) = 'V' THEN d.hours ELSE 0 END) AS vacation_hours,
               SUM(CASE WHEN UPPER(COALESCE(d.day_code, '')) IN ('Z', 'ZW') THEN d.hours ELSE 0 END) AS sickness_hours,
               SUM(CASE WHEN UPPER(COALESCE(d.day_code, '')) = 'RV' THEN d.hours ELSE 0 END) AS rv_hours,
               SUM(CASE WHEN UPPER(COALESCE(d.day_code, '')) IN ('KV', 'C', 'A') THEN d.hours ELSE 0 END) AS kv_hours,
               SUM(CASE WHEN UPPER(COALESCE(d.day_code, '')) = 'F' THEN d.hours ELSE 0 END) AS holiday_hours
        FROM payroll_week_input_days d
        WHERE d.payroll_week_input_id = i.id
    ) day_totals ON TRUE
    LEFT JOIN LATERAL (
        SELECT SUM(COALESCE(pa.amount, 0)) AS day_allowance_amount
        FROM payroll_employee_allowances pa
        WHERE pa.arrangement_id = i.arrangement_id
          AND pa.unit = 'day'
    ) allowance_totals ON TRUE
), parameter_rates AS (
    SELECT b.*,
           COALESCE(
               b.own_transport_km_rate,
               CASE
                   WHEN LOWER(COALESCE(b.cao_branch, '')) LIKE '%uta%' THEN uta_rate.uta_value
                   ELSE build_rate.build_value
               END,
               0
           ) AS selected_travel_rate
    FROM input_base b
    LEFT JOIN LATERAL (
        SELECT v.uta_value
        FROM payroll_parameters p
        JOIN payroll_parameter_versions v ON v.parameter_id = p.id
        WHERE p.parameter_key = 'travel_km_net_uta'
          AND (v.year = b.year OR v.year IS NULL)
          AND (v.period_number <= b.period_number OR v.period_number IS NULL)
        ORDER BY v.year DESC NULLS LAST, v.period_number DESC NULLS LAST, v.id DESC
        LIMIT 1
    ) uta_rate ON TRUE
    LEFT JOIN LATERAL (
        SELECT v.build_value
        FROM payroll_parameters p
        JOIN payroll_parameter_versions v ON v.parameter_id = p.id
        WHERE p.parameter_key = 'travel_km_net_build'
          AND (v.year = b.year OR v.year IS NULL)
          AND (v.period_number <= b.period_number OR v.period_number IS NULL)
        ORDER BY v.year DESC NULLS LAST, v.period_number DESC NULLS LAST, v.id DESC
        LIMIT 1
    ) build_rate ON TRUE
), calculated AS (
    SELECT *,
           ROUND(COALESCE(net_base_40h, 0) * COALESCE(worked_hours, 0) / 40, 2) AS calculated_net_wage,
           ROUND(COALESCE(vacation_rate_40h, net_base_40h, 0) * COALESCE(vacation_hours + rv_hours + kv_hours, 0) / 40, 2) AS calculated_leave_wage,
           ROUND(COALESCE(sickness_rate_40h, vacation_rate_40h, net_base_40h, 0) * COALESCE(sickness_hours, 0) / 40, 2) AS calculated_sickness_wage,
           ROUND(COALESCE(holiday_rate_40h, vacation_rate_40h, net_base_40h, 0) * COALESCE(holiday_hours, 0) / 40, 2) AS calculated_holiday_wage,
           CASE
               WHEN company_car THEN 0
               ELSE ROUND(COALESCE(total_km, 0) * COALESCE(selected_travel_rate, 0), 2)
           END AS calculated_travel,
           ROUND(COALESCE(worked_days, 0) * COALESCE(day_allowance_per_day, 0), 2) AS calculated_day_allowance
    FROM parameter_rates
)
INSERT INTO payroll_week_results (
    payroll_week_input_id,
    payroll_period_id,
    payroll_period_week_id,
    relation_id,
    arrangement_id,
    employee_name,
    week_number,
    worked_days,
    worked_hours,
    vacation_hours,
    sickness_hours,
    rv_hours,
    kv_hours,
    holiday_hours,
    total_km,
    net_wage_amount,
    travel_amount,
    day_allowance_amount,
    extra_net_amount,
    net_week_total,
    travel_rate,
    calculation_status,
    calculation_details,
    calculated_at,
    created_at,
    updated_at
)
SELECT payroll_week_input_id,
       payroll_period_id,
       payroll_period_week_id,
       relation_id,
       arrangement_id,
       employee_name,
       week_number,
       worked_days,
       worked_hours,
       vacation_hours,
       sickness_hours,
       rv_hours,
       kv_hours,
       holiday_hours,
       total_km,
       calculated_net_wage + calculated_leave_wage + calculated_sickness_wage + calculated_holiday_wage,
       calculated_travel,
       calculated_day_allowance,
       0,
       calculated_net_wage + calculated_leave_wage + calculated_sickness_wage + calculated_holiday_wage + calculated_travel + calculated_day_allowance,
       selected_travel_rate,
       CASE
           WHEN arrangement_id IS NULL THEN 'mist_inrichting'
           WHEN net_base_40h IS NULL THEN 'mist_netto_basisloon'
           ELSE 'concept'
       END,
       jsonb_build_object(
           'formula', 'netto loon per uursoort + reiskosten + dagvergoedingen',
           'net_base_40h', net_base_40h,
           'travel_rate', selected_travel_rate,
           'company_car', company_car,
           'day_allowance_per_day', day_allowance_per_day
       ),
       NOW(),
       NOW(),
       NOW()
FROM calculated
ON CONFLICT (payroll_week_input_id)
DO UPDATE SET
    payroll_period_id = EXCLUDED.payroll_period_id,
    payroll_period_week_id = EXCLUDED.payroll_period_week_id,
    relation_id = EXCLUDED.relation_id,
    arrangement_id = EXCLUDED.arrangement_id,
    employee_name = EXCLUDED.employee_name,
    week_number = EXCLUDED.week_number,
    worked_days = EXCLUDED.worked_days,
    worked_hours = EXCLUDED.worked_hours,
    vacation_hours = EXCLUDED.vacation_hours,
    sickness_hours = EXCLUDED.sickness_hours,
    rv_hours = EXCLUDED.rv_hours,
    kv_hours = EXCLUDED.kv_hours,
    holiday_hours = EXCLUDED.holiday_hours,
    total_km = EXCLUDED.total_km,
    net_wage_amount = EXCLUDED.net_wage_amount,
    travel_amount = EXCLUDED.travel_amount,
    day_allowance_amount = EXCLUDED.day_allowance_amount,
    extra_net_amount = EXCLUDED.extra_net_amount,
    net_week_total = EXCLUDED.net_week_total,
    travel_rate = EXCLUDED.travel_rate,
    calculation_status = EXCLUDED.calculation_status,
    calculation_details = EXCLUDED.calculation_details,
    calculated_at = NOW(),
    updated_at = NOW();
