CREATE OR REPLACE VIEW payroll_year_overview AS
SELECT y.id AS payroll_year_id,
       y.year,
       y.period_count AS expected_period_count,
       y.weeks_per_period AS expected_weeks_per_period,
       COUNT(DISTINCT p.id) AS actual_period_count,
       COUNT(DISTINCT w.id) AS actual_week_count,
       MIN(p.start_date) AS first_period_start_date,
       MAX(p.end_date) AS last_period_end_date,
       y.status,
       y.updated_at
FROM payroll_years y
LEFT JOIN payroll_periods p ON p.payroll_year_id = y.id OR (p.payroll_year_id IS NULL AND p.year = y.year)
LEFT JOIN payroll_period_weeks w ON w.payroll_period_id = p.id
GROUP BY y.id, y.year, y.period_count, y.weeks_per_period, y.status, y.updated_at;

CREATE OR REPLACE VIEW payroll_period_datamodel_status AS
SELECT p.id AS payroll_period_id,
       COALESCE(y.year, p.year) AS year,
       p.period_number,
       p.name AS period_name,
       p.start_date,
       p.end_date,
       p.status AS period_status,
       COALESCE(week_counts.week_count, 0) AS week_count,
       COALESCE(input_counts.week_input_count, 0) AS week_input_count,
       COALESCE(line_counts.week_line_count, 0) AS week_line_count,
       COALESCE(result_counts.week_result_count, 0) AS week_result_count,
       COALESCE(settlement_counts.period_settlement_count, 0) AS period_settlement_count,
       COALESCE(arrangement_counts.employee_arrangement_count, 0) AS employee_arrangement_count,
       COALESCE(parameter_counts.parameter_version_count, 0) AS parameter_version_count,
       COALESCE(balance_counts.running_balance_account_count, 0) AS running_balance_account_count,
       COALESCE(balance_counts.running_balance_mutation_count, 0) AS running_balance_mutation_count,
       COALESCE(audit_counts.audit_event_count, 0) AS audit_event_count,
       COALESCE(openai_counts.openai_api_audit_event_count, 0) AS openai_api_audit_event_count,
       CASE
           WHEN COALESCE(week_counts.week_count, 0) = 4 THEN 'ok'
           WHEN COALESCE(week_counts.week_count, 0) = 0 THEN 'mist weken'
           ELSE 'onvolledig'
       END AS week_structure_status,
       p.updated_at
FROM payroll_periods p
LEFT JOIN payroll_years y ON y.id = p.payroll_year_id OR (p.payroll_year_id IS NULL AND y.year = p.year)
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS week_count
    FROM payroll_period_weeks w
    WHERE w.payroll_period_id = p.id
) week_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS week_input_count
    FROM payroll_week_inputs i
    WHERE i.payroll_period_id = p.id
) input_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS week_line_count
    FROM payroll_week_lines l
    WHERE l.payroll_period_id = p.id
) line_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS week_result_count
    FROM payroll_week_results r
    WHERE r.payroll_period_id = p.id
) result_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS period_settlement_count
    FROM payroll_period_settlements s
    WHERE s.payroll_period_id = p.id
) settlement_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS employee_arrangement_count
    FROM payroll_employee_arrangements a
    WHERE a.valid_from_year = p.year
      AND a.valid_from_period_number = p.period_number
) arrangement_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS parameter_version_count
    FROM payroll_parameter_versions v
    WHERE v.year = p.year
      AND v.period_number = p.period_number
) parameter_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(DISTINCT a.id) AS running_balance_account_count,
           COUNT(m.id) AS running_balance_mutation_count
    FROM payroll_running_balance_accounts a
    LEFT JOIN payroll_running_balance_mutations m ON m.account_id = a.id
    WHERE a.balance_year IN (0, p.year)
) balance_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS audit_event_count
    FROM audit_events e
    WHERE e.entity_type = 'payroll_period'
      AND e.entity_id = p.id
) audit_counts ON TRUE
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS openai_api_audit_event_count
    FROM openai_api_audit_events a
    JOIN payroll_week_inputs i ON i.id = a.payroll_week_input_id
    WHERE i.payroll_period_id = p.id
) openai_counts ON TRUE;

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
    'Payroll datamodel controleviews toegevoegd',
    'payroll_datamodel',
    'Controleviews',
    'Views payroll_year_overview en payroll_period_datamodel_status toegevoegd voor controle van het payroll-fundament.',
    'Systeem',
    jsonb_build_object(
        'views', jsonb_build_array('payroll_year_overview', 'payroll_period_datamodel_status'),
        'source', 'migrations/038_payroll_datamodel_views.sql'
    ),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM audit_events
    WHERE action = 'Payroll datamodel controleviews toegevoegd'
      AND entity_type = 'payroll_datamodel'
);
