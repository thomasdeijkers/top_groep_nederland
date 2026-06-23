from pathlib import Path

from shared.db.connection import get_connection


_TABLES_READY = False


def _payroll_test_seed_is_suppressed(conn) -> bool:
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.audit_events');")
            if not cursor.fetchone()[0]:
                return False
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM audit_events
                    WHERE entity_type = 'payroll_test_reset'
                      AND action = 'Testfase uren en loonperiodes geleegd'
                );
                """
            )
            return bool(cursor.fetchone()[0])
    except Exception:
        return False


def ensure_dashboard_tables():
    global _TABLES_READY
    if _TABLES_READY:
        return

    migrations = [
        Path("migrations/001_otys_organizations.sql"),
        Path("migrations/002_candidates_principals_tickets.sql"),
        Path("migrations/003_vacancies.sql"),
        Path("migrations/004_relation_edit_fields.sql"),
        Path("migrations/005_vacancy_edit_fields.sql"),
        Path("migrations/006_whatsapp_timesheet_inbox.sql"),
        Path("migrations/007_whatsapp_upload_fields.sql"),
        Path("migrations/008_timesheet_corrections.sql"),
        Path("migrations/009_whatsapp_archive_delete.sql"),
        Path("migrations/010_unified_relations.sql"),
        Path("migrations/011_relation_profile_image.sql"),
        Path("migrations/012_openai_usage.sql"),
        Path("migrations/013_timesheet_workflow_booking.sql"),
        Path("migrations/014_timesheet_source_channel.sql"),
        Path("migrations/015_relation_address_archive.sql"),
        Path("migrations/016_payroll_cao_settings.sql"),
        Path("migrations/017_project_cao_link.sql"),
        Path("migrations/018_payroll_periods.sql"),
        Path("migrations/021_audit_events.sql"),
        Path("migrations/022_otys_staging_tables.sql"),
        Path("migrations/023_otys_api_usage.sql"),
        Path("migrations/024_otys_relations_backfill.sql"),
        Path("migrations/025_dashboard_performance_indexes.sql"),
        Path("migrations/026_payroll_excel_reference.sql"),
        Path("migrations/027_payroll_workbook_cell_overrides.sql"),
        Path("migrations/029_relation_payroll_settings.sql"),
        Path("migrations/030_openai_api_audit_events.sql"),
        Path("migrations/031_payroll_parameters.sql"),
        Path("migrations/032_payroll_employee_arrangements.sql"),
        Path("migrations/033_payroll_week_inputs.sql"),
        Path("migrations/034_payroll_week_results.sql"),
        Path("migrations/035_payroll_period_settlements.sql"),
        Path("migrations/036_payroll_running_balances.sql"),
        Path("migrations/037_payroll_datamodel_foundation.sql"),
        Path("migrations/038_payroll_datamodel_views.sql"),
        Path("migrations/042_payroll_audit_context.sql"),
        Path("migrations/045_restore_payroll_period_calendar.sql"),
        Path("migrations/046_clear_legacy_timesheet_candidate_fk.sql"),
    ]

    optional_migrations = set()

    with get_connection() as conn:
        for migration in migrations:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(migration.read_text(encoding="utf-8"))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print(f"DASHBOARD_MIGRATION_ERROR {migration}: {type(exc).__name__}: {exc}")
                if migration.name not in optional_migrations:
                    raise
    _TABLES_READY = True
