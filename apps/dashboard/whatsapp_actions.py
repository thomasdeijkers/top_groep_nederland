from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


def archive_whatsapp_timesheet(timesheet_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET archived_at = NOW(),
                    status = 'gearchiveerd',
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (timesheet_id,),
            )
            cursor.execute(
                """
                DELETE FROM payroll_week_inputs
                WHERE timesheet_inbox_id = %s;
                """,
                (timesheet_id,),
            )
        conn.commit()


def delete_whatsapp_timesheet(timesheet_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET deleted_at = NOW(),
                    status = 'verwijderd',
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (timesheet_id,),
            )
            cursor.execute(
                """
                DELETE FROM payroll_week_inputs
                WHERE timesheet_inbox_id = %s;
                """,
                (timesheet_id,),
            )
        conn.commit()
