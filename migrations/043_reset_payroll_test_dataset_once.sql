DO $$
DECLARE
    table_name TEXT;
    deleted_counts JSONB := '{}'::jsonb;
    deleted_count INTEGER;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM audit_events
        WHERE entity_type = 'payroll_test_reset'
          AND metadata->>'source_channel' = 'deploy_reset_043'
    ) THEN
        RETURN;
    END IF;

    FOREACH table_name IN ARRAY ARRAY[
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
    ] LOOP
        IF to_regclass('public.' || table_name) IS NOT NULL THEN
            EXECUTE format('DELETE FROM %I', table_name);
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            deleted_counts := deleted_counts || jsonb_build_object(table_name, deleted_count);
        END IF;
    END LOOP;

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
        'Eenmalige deploy-reset heeft de testdataset geleegd.',
        'Verwijderd',
        jsonb_build_object(
            'source_channel', 'deploy_reset_043',
            'deleted_tables', deleted_counts
        ),
        'deploy_reset_043',
        NOW()
    );
END $$;
