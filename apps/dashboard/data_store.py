from pathlib import Path

from shared.db.connection import get_connection


_TABLES_READY = False


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
        Path("migrations/019_demo_seed_data.sql"),
        Path("migrations/020_demo_payroll_period.sql"),
        Path("migrations/021_audit_events.sql"),
        Path("migrations/022_otys_staging_tables.sql"),
        Path("migrations/023_otys_api_usage.sql"),
        Path("migrations/024_otys_relations_backfill.sql"),
        Path("migrations/025_dashboard_performance_indexes.sql"),
        Path("migrations/026_payroll_excel_reference.sql"),
        Path("migrations/027_payroll_workbook_cell_overrides.sql"),
        Path("migrations/028_payroll_period_02_test_timesheets.sql"),
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
        conn.commit()
    _TABLES_READY = True
