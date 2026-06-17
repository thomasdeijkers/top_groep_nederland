CREATE TABLE IF NOT EXISTS payroll_running_balance_accounts (
    id SERIAL PRIMARY KEY,
    relation_id INTEGER NOT NULL REFERENCES relations(id) ON DELETE CASCADE,
    balance_type TEXT NOT NULL CHECK (balance_type IN ('wkr', 'loan_advance', 'choice_budget')),
    balance_label TEXT NOT NULL,
    balance_year INTEGER NOT NULL DEFAULT 0,
    annual_limit NUMERIC(12,2),
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT NOT NULL DEFAULT 'dashboard',
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE (relation_id, balance_type, balance_year)
);

CREATE TABLE IF NOT EXISTS payroll_running_balance_mutations (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES payroll_running_balance_accounts(id) ON DELETE CASCADE,
    payroll_period_id INTEGER REFERENCES payroll_periods(id) ON DELETE SET NULL,
    mutation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    amount NUMERIC(12,2) NOT NULL,
    description TEXT,
    source TEXT NOT NULL DEFAULT 'dashboard',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payroll_running_balance_accounts_relation
    ON payroll_running_balance_accounts (relation_id, balance_type, balance_year);

CREATE INDEX IF NOT EXISTS idx_payroll_running_balance_mutations_account
    ON payroll_running_balance_mutations (account_id, mutation_date DESC, id DESC);

WITH balance_seed(balance_type, balance_label, balance_year, annual_limit) AS (
    VALUES
        ('wkr', 'WKR-teller', 2026, 2400.00),
        ('loan_advance', 'Loonvoorschot / geldlening', 0, NULL),
        ('choice_budget', 'Keuzebudget', 0, NULL)
), candidate_relations AS (
    SELECT DISTINCT r.id AS relation_id
    FROM relations r
    LEFT JOIN payroll_employee_arrangements a ON a.relation_id = r.id
    LEFT JOIN payroll_period_settlements s ON s.relation_id = r.id
    WHERE r.relation_type = 'candidate'
      AND r.archived_at IS NULL
      AND (
          a.id IS NOT NULL
          OR s.id IS NOT NULL
          OR COALESCE(r.payroll_choice_budget, '') <> ''
      )
)
INSERT INTO payroll_running_balance_accounts (
    relation_id,
    balance_type,
    balance_label,
    balance_year,
    annual_limit,
    source,
    created_at,
    updated_at
)
SELECT c.relation_id,
       s.balance_type,
       s.balance_label,
       s.balance_year,
       s.annual_limit,
       'migration_seed',
       NOW(),
       NOW()
FROM candidate_relations c
CROSS JOIN balance_seed s
ON CONFLICT (relation_id, balance_type, balance_year)
DO UPDATE SET
    balance_label = EXCLUDED.balance_label,
    annual_limit = EXCLUDED.annual_limit,
    updated_at = NOW();

WITH choice_budget_seed AS (
    SELECT a.id AS account_id,
           r.payroll_choice_budget AS raw_value,
           CASE
               WHEN COALESCE(r.payroll_choice_budget, '') ~ '^-?[0-9]+([,.][0-9]+)?$'
               THEN REPLACE(r.payroll_choice_budget, ',', '.')::numeric
               ELSE NULL
           END AS numeric_value
    FROM payroll_running_balance_accounts a
    JOIN relations r ON r.id = a.relation_id
    WHERE a.balance_type = 'choice_budget'
      AND COALESCE(r.payroll_choice_budget, '') <> ''
)
INSERT INTO payroll_running_balance_mutations (
    account_id,
    amount,
    description,
    source,
    created_at,
    updated_at
)
SELECT account_id,
       numeric_value,
       'Startsaldo keuzebudget uit bestaande relatie-inrichting',
       'legacy_relation_fields',
       NOW(),
       NOW()
FROM choice_budget_seed s
WHERE s.numeric_value IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM payroll_running_balance_mutations existing
      WHERE existing.account_id = s.account_id
        AND existing.source = 'legacy_relation_fields'
  );
