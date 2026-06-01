from pathlib import Path

from shared.db.connection import get_connection


def ensure_dashboard_tables():
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
    ]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for migration in migrations:
                cursor.execute(migration.read_text(encoding="utf-8"))
        conn.commit()
