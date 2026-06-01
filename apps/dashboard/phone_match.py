import re

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if digits.startswith("0031"):
        digits = "31" + digits[4:]
    if digits.startswith("0"):
        digits = "31" + digits[1:]
    return digits


def find_candidate_by_phone(phone: str) -> dict | None:
    normalized = normalize_phone(phone)
    if not normalized:
        return None

    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, phone
                FROM relations
                WHERE relation_type = 'candidate'
                  AND archived_at IS NULL
                  AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                  AND (
                    regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') LIKE %s
                    OR regexp_replace(COALESCE(phone, ''), '\\D', '', 'g') LIKE %s
                  )
                ORDER BY updated_at DESC, id DESC
                LIMIT 1;
                """,
                (f"%{normalized[-9:]}", f"%{normalized[-10:]}"),
            )
            row = cursor.fetchone()

    if not row:
        return None

    return {"id": row[0], "name": row[1], "phone": row[2]}
