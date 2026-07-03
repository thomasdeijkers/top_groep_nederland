ALTER TABLE payroll_week_inputs
    ADD COLUMN IF NOT EXISTS payroll_status TEXT NOT NULL DEFAULT 'loon_berekenen';

UPDATE payroll_week_inputs
SET payroll_status = CASE
        WHEN LOWER(REPLACE(COALESCE(status, ''), ' ', '_')) IN ('uit_te_betalen', 'uitbetaald')
            THEN LOWER(REPLACE(COALESCE(status, ''), ' ', '_'))
        WHEN COALESCE(payroll_status, '') = ''
            THEN LOWER(REPLACE(COALESCE(status, 'loon_berekenen'), ' ', '_'))
        ELSE LOWER(REPLACE(payroll_status, ' ', '_'))
    END,
    updated_at = NOW()
WHERE COALESCE(payroll_status, '') = ''
   OR payroll_status <> LOWER(REPLACE(payroll_status, ' ', '_'))
   OR LOWER(REPLACE(COALESCE(status, ''), ' ', '_')) IN ('uit_te_betalen', 'uitbetaald');

CREATE INDEX IF NOT EXISTS idx_payroll_week_inputs_payment_status
    ON payroll_week_inputs (payroll_period_id, payroll_status);
