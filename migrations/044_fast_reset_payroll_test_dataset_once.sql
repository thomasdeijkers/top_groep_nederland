DO $$
DECLARE
    reset_tables TEXT[] := ARRAY[
        'payroll_workbook_cell_overrides',
        'openai_api_audit_events',
        'openai_usage_events',
        'payroll_running_balance_mutations',
        'payroll_running_balance_accounts',
        'payroll_period_settlements',
        'payroll_calculation_results',
        'payroll_period_totals',
        'payroll_week_results',
        'payroll_week_lines',
        'payroll_week_input_projects',
        'payroll_week_input_days',
        'payroll_week_inputs',
        'payroll_week_entries',
        'payroll_import_logs',
        'payroll_employee_settings',
        'payroll_employee_rights',
        'payroll_employee_allowances',
        'payroll_employee_arrangements',
        'project_time_bookings',
        'timesheet_field_corrections',
        'whatsapp_timesheet_inbox',
        'payroll_period_weeks',
        'payroll_periods',
        'payroll_employees',
        'audit_log'
    ];
    table_name TEXT;
    existing_tables TEXT := '';
BEGIN
    IF EXISTS (
        SELECT 1
        FROM audit_events
        WHERE entity_type = 'payroll_test_reset'
          AND metadata->>'source_channel' = 'deploy_reset_044'
    ) THEN
        RETURN;
    END IF;

    FOREACH table_name IN ARRAY reset_tables LOOP
        IF to_regclass('public.' || table_name) IS NOT NULL THEN
            existing_tables := existing_tables || CASE WHEN existing_tables = '' THEN '' ELSE ', ' END || quote_ident(table_name);
        END IF;
    END LOOP;

    IF existing_tables <> '' THEN
        EXECUTE 'TRUNCATE TABLE ' || existing_tables || ' RESTART IDENTITY CASCADE';
    END IF;

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
    VALUES (
        'Deploy',
        'Testfase uren en loonperiodes geleegd',
        'payroll_test_reset',
        'Urenbriefjes en loonperiodes',
        'Snelle deploy-reset heeft de testdataset opnieuw geleegd.',
        'Verwijderd',
        jsonb_build_object('source_channel', 'deploy_reset_044'),
        'deploy_reset_044',
        NOW()
    );
END $$;
