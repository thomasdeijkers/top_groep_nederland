CREATE TABLE IF NOT EXISTS payroll_employee_arrangements (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE SET NULL,
    valid_from_year INTEGER NOT NULL,
    valid_from_period_number INTEGER NOT NULL CHECK (valid_from_period_number BETWEEN 1 AND 13),
    valid_until_year INTEGER,
    valid_until_period_number INTEGER CHECK (valid_until_period_number IS NULL OR valid_until_period_number BETWEEN 1 AND 13),
    cao_branch TEXT NOT NULL DEFAULT 'bouwplaats',
    phase TEXT,
    pension_scheme TEXT,
    contract_hours_4w NUMERIC(10,2),
    days_right_code TEXT,
    scale_code TEXT,
    function_name TEXT,
    gross_hourly_wage NUMERIC(12,4),
    net_base_40h NUMERIC(12,2),
    net_reference_week NUMERIC(12,2),
    vacation_rate_40h NUMERIC(12,2),
    sickness_rate_40h NUMERIC(12,2),
    holiday_rate_40h NUMERIC(12,2),
    payment_schedule TEXT NOT NULL DEFAULT 'weekly' CHECK (payment_schedule IN ('weekly', 'four_weekly')),
    company_car BOOLEAN NOT NULL DEFAULT FALSE,
    license_plate TEXT,
    own_transport_km_rate NUMERIC(10,4),
    health_insurance_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'concept',
    source TEXT NOT NULL DEFAULT 'dashboard',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (relation_id, valid_from_year, valid_from_period_number)
);

CREATE TABLE IF NOT EXISTS payroll_employee_rights (
    id SERIAL PRIMARY KEY,
    arrangement_id INTEGER NOT NULL REFERENCES payroll_employee_arrangements(id) ON DELETE CASCADE,
    right_code TEXT NOT NULL,
    right_name TEXT NOT NULL,
    days NUMERIC(10,2) NOT NULL DEFAULT 0,
    handling TEXT NOT NULL CHECK (handling IN ('reserve', 'compensate', 'tsf')),
    percentage NUMERIC(12,6),
    source TEXT NOT NULL DEFAULT 'dashboard',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (arrangement_id, right_code, handling)
);

CREATE TABLE IF NOT EXISTS payroll_employee_allowances (
    id SERIAL PRIMARY KEY,
    arrangement_id INTEGER NOT NULL REFERENCES payroll_employee_arrangements(id) ON DELETE CASCADE,
    allowance_key TEXT NOT NULL,
    name TEXT NOT NULL,
    fiscal_category TEXT NOT NULL CHECK (fiscal_category IN ('WKR', 'GV', 'IK', 'netto', 'bruto')),
    unit TEXT NOT NULL DEFAULT 'day',
    default_parameter_id INTEGER REFERENCES payroll_parameters(id) ON DELETE SET NULL,
    amount NUMERIC(12,4),
    source TEXT NOT NULL DEFAULT 'dashboard',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (arrangement_id, allowance_key)
);

CREATE INDEX IF NOT EXISTS idx_payroll_employee_arrangements_relation
    ON payroll_employee_arrangements (relation_id, valid_from_year, valid_from_period_number);

CREATE INDEX IF NOT EXISTS idx_payroll_employee_arrangements_period
    ON payroll_employee_arrangements (valid_from_year, valid_from_period_number, status);

CREATE INDEX IF NOT EXISTS idx_payroll_employee_rights_arrangement
    ON payroll_employee_rights (arrangement_id);

CREATE INDEX IF NOT EXISTS idx_payroll_employee_allowances_arrangement
    ON payroll_employee_allowances (arrangement_id);

INSERT INTO payroll_employee_arrangements (
    relation_id,
    valid_from_year,
    valid_from_period_number,
    phase,
    pension_scheme,
    contract_hours_4w,
    days_right_code,
    scale_code,
    function_name,
    gross_hourly_wage,
    license_plate,
    status,
    source,
    notes,
    created_at,
    updated_at
)
SELECT r.id,
       2026,
       1,
       NULLIF(r.payroll_phase, ''),
       NULLIF(r.payroll_pension, ''),
       CASE
           WHEN COALESCE(r.payroll_cao_hours, '') ~ '^[0-9]+([,.][0-9]+)?$'
           THEN REPLACE(r.payroll_cao_hours, ',', '.')::numeric
           ELSE NULL
       END,
       NULLIF(r.payroll_days_right, ''),
       NULLIF(r.payroll_scale, ''),
       NULLIF(r.payroll_function, ''),
       CASE
           WHEN COALESCE(r.payroll_hourly_wage, '') ~ '^[0-9]+([,.][0-9]+)?$'
           THEN REPLACE(r.payroll_hourly_wage, ',', '.')::numeric
           ELSE NULL
       END,
       NULLIF(r.payroll_license_plate, ''),
       'concept',
       'legacy_relation_fields',
       'Eerste concept-inrichting overgenomen uit bestaande relatievelden.',
       NOW(),
       NOW()
FROM relations r
WHERE r.relation_type = 'candidate'
  AND (
      COALESCE(r.payroll_phase, '') <> ''
      OR COALESCE(r.payroll_pension, '') <> ''
      OR COALESCE(r.payroll_cao_hours, '') <> ''
      OR COALESCE(r.payroll_days_right, '') <> ''
      OR COALESCE(r.payroll_scale, '') <> ''
      OR COALESCE(r.payroll_function, '') <> ''
      OR COALESCE(r.payroll_hourly_wage, '') <> ''
      OR COALESCE(r.payroll_license_plate, '') <> ''
  )
ON CONFLICT (relation_id, valid_from_year, valid_from_period_number)
DO UPDATE SET
    phase = COALESCE(EXCLUDED.phase, payroll_employee_arrangements.phase),
    pension_scheme = COALESCE(EXCLUDED.pension_scheme, payroll_employee_arrangements.pension_scheme),
    contract_hours_4w = COALESCE(EXCLUDED.contract_hours_4w, payroll_employee_arrangements.contract_hours_4w),
    days_right_code = COALESCE(EXCLUDED.days_right_code, payroll_employee_arrangements.days_right_code),
    scale_code = COALESCE(EXCLUDED.scale_code, payroll_employee_arrangements.scale_code),
    function_name = COALESCE(EXCLUDED.function_name, payroll_employee_arrangements.function_name),
    gross_hourly_wage = COALESCE(EXCLUDED.gross_hourly_wage, payroll_employee_arrangements.gross_hourly_wage),
    license_plate = COALESCE(EXCLUDED.license_plate, payroll_employee_arrangements.license_plate),
    updated_at = NOW();
