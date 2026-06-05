from psycopg2.extras import Json
from decimal import Decimal

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


def save_field_corrections(timesheet_id: int, corrections: dict[str, str], matched_relation_id: int | None = None) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT parsed_fields FROM whatsapp_timesheet_inbox WHERE id = %s;",
                (timesheet_id,),
            )
            row = cursor.fetchone()
            if not row:
                return

            parsed_fields = row[0] or {}
            original_totals = {
                "total_hours": (parsed_fields.get("total_hours") or {}).get("value"),
                "total_km": (parsed_fields.get("total_km") or {}).get("value"),
            }
            for field_key, corrected_value in corrections.items():
                corrected_value = (corrected_value or "").strip()

                original = parsed_fields.get(field_key, {})
                original_value = str(original.get("value", ""))
                original_confidence = original.get("confidence", 0)
                parsed_fields[field_key] = {
                    "value": corrected_value,
                    "confidence": 98 if corrected_value else 0,
                    "corrected": True,
                }
                if not corrected_value and not original_value:
                    continue
                cursor.execute(
                    """
                    INSERT INTO timesheet_field_corrections (
                        timesheet_inbox_id,
                        field_key,
                        original_value,
                        corrected_value,
                        original_confidence
                    )
                    VALUES (%s, %s, %s, %s, %s);
                    """,
                    (timesheet_id, field_key, original_value, corrected_value, original_confidence),
                )

            matched_candidate_name = None
            matched_candidate_phone = None
            if matched_relation_id:
                cursor.execute(
                    """
                    SELECT name, phone
                    FROM relations
                    WHERE id = %s
                      AND relation_type = 'candidate'
                      AND archived_at IS NULL;
                    """,
                    (matched_relation_id,),
                )
                candidate_row = cursor.fetchone()
                if candidate_row:
                    matched_candidate_name = candidate_row[0]
                    matched_candidate_phone = candidate_row[1]
                    parsed_fields["employee_name"] = {
                        "value": matched_candidate_name or corrections.get("employee_name", ""),
                        "confidence": 98,
                        "corrected": True,
                    }
                    if matched_candidate_phone:
                        parsed_fields["employee_phone"] = {
                            "value": matched_candidate_phone,
                            "confidence": 98,
                            "corrected": True,
                        }

            _apply_absence_code_to_day_codes(parsed_fields)
            _recalculate_total_checks(parsed_fields, original_totals)
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET parsed_fields = %s,
                    matched_relation_id = COALESCE(%s, matched_relation_id),
                    matched_candidate_name = COALESCE(%s, matched_candidate_name),
                    employee_name = COALESCE(%s, NULLIF(%s, ''), employee_name),
                    sender_phone = COALESCE(%s, NULLIF(%s, ''), sender_phone),
                    overall_confidence = LEAST(98, GREATEST(COALESCE(overall_confidence, 0), 80)),
                    status = 'goed_te_keuren',
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (
                    Json(parsed_fields),
                    matched_relation_id,
                    matched_candidate_name,
                    matched_candidate_name,
                    corrections.get("employee_name", ""),
                    matched_candidate_phone,
                    corrections.get("employee_phone", ""),
                    timesheet_id,
                ),
            )
        conn.commit()


def validate_timesheet(timesheet_id: int, principal_id: int | None, project_id: int | None) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT matched_relation_id, work_date, hours, parsed_fields
                FROM whatsapp_timesheet_inbox
                WHERE id = %s;
                """,
                (timesheet_id,),
            )
            row = cursor.fetchone()
            if not row:
                return

            relation_id, work_date, hours, parsed_fields = row
            parsed_fields = parsed_fields or {}
            hours = hours or _hours_from_fields(parsed_fields)
            payroll_cao_setting_id = _project_cao_setting_id(cursor, project_id)

            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET selected_principal_id = %s,
                    selected_project_id = %s,
                    status = 'loon_te_berekenen',
                    validated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (principal_id, project_id, timesheet_id),
            )
            cursor.execute(
                """
                INSERT INTO project_time_bookings (
                    timesheet_inbox_id, relation_id, principal_id, project_id,
                    payroll_cao_setting_id, work_date, hours, status, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'loon_te_berekenen', NOW());
                """,
                (timesheet_id, relation_id, principal_id, project_id, payroll_cao_setting_id, work_date, hours),
            )
        conn.commit()


def send_to_payroll(timesheet_id: int) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET status = 'doorgestuurd_naar_loonadministratie',
                    payroll_sent_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (timesheet_id,),
            )
            cursor.execute(
                """
                UPDATE project_time_bookings
                SET status = 'doorgestuurd_naar_loonadministratie',
                    updated_at = NOW()
                WHERE timesheet_inbox_id = %s;
                """,
                (timesheet_id,),
            )
        conn.commit()


def _hours_from_fields(parsed_fields: dict):
    total = parsed_fields.get("total_hours", {}).get("value")
    try:
        return str(total).replace(",", ".") if str(total or "").strip() else None
    except Exception:
        return None


def _project_cao_setting_id(cursor, project_id: int | None):
    if not project_id:
        return None
    cursor.execute(
        """
        SELECT payroll_cao_setting_id
        FROM vacancies
        WHERE id = %s;
        """,
        (project_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _apply_absence_code_to_day_codes(parsed_fields: dict) -> None:
    absence_code = str((parsed_fields.get("absence_code") or {}).get("value") or "").strip()
    if not absence_code:
        return
    day_pairs = (
        ("monday_code", "monday_hours"),
        ("tuesday_code", "tuesday_hours"),
        ("wednesday_code", "wednesday_hours"),
        ("thursday_code", "thursday_hours"),
        ("friday_code", "friday_hours"),
        ("saturday_code", "saturday_hours"),
        ("sunday_code", "sunday_hours"),
    )
    for code_key, hours_key in day_pairs:
        code_value = str((parsed_fields.get(code_key) or {}).get("value") or "").strip()
        hours_value = _decimal_or_none((parsed_fields.get(hours_key) or {}).get("value"))
        if not code_value and (hours_value is None or hours_value == 0):
            parsed_fields[code_key] = {
                "value": absence_code,
                "confidence": 98,
                "corrected": True,
            }


def _decimal_or_none(value):
    try:
        text = str(value or "").replace(",", ".").strip()
        return Decimal(text) if text else None
    except Exception:
        return None


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _recalculate_total_checks(parsed_fields: dict, original_totals: dict | None = None) -> None:
    original_totals = original_totals or {}
    _recalculate_sum_check(
        parsed_fields,
        ("monday_hours", "tuesday_hours", "wednesday_hours", "thursday_hours", "friday_hours", "saturday_hours", "sunday_hours"),
        "total_hours",
        "calculated_total_hours",
        "total_hours_check",
        "uur",
        "totaal ontbreekt",
        original_totals.get("total_hours"),
    )
    _recalculate_sum_check(
        parsed_fields,
        ("monday_km", "tuesday_km", "wednesday_km", "thursday_km", "friday_km", "saturday_km", "sunday_km"),
        "total_km",
        "calculated_total_km",
        "total_km_check",
        "km",
        "totaal km ontbreekt",
        original_totals.get("total_km"),
    )


def _recalculate_sum_check(
    parsed_fields: dict,
    day_keys: tuple[str, ...],
    total_key: str,
    calculated_key: str,
    check_key: str,
    unit: str,
    missing_message: str,
    original_total_value=None,
) -> None:
    values = [_decimal_or_none((parsed_fields.get(key) or {}).get("value")) for key in day_keys]
    known_values = [value for value in values if value is not None]
    if not known_values:
        parsed_fields[calculated_key] = {"value": "", "confidence": 0, "corrected": True}
        parsed_fields[check_key] = {"value": "", "confidence": 0, "corrected": True}
        return

    calculated = sum(known_values, Decimal("0"))
    calculated_text = _format_decimal(calculated)
    parsed_fields[calculated_key] = {"value": calculated_text, "confidence": 98, "corrected": True}
    original_total = _decimal_or_none(original_total_value)
    stated_total = original_total if original_total is not None else _decimal_or_none((parsed_fields.get(total_key) or {}).get("value"))
    parsed_fields[total_key] = {"value": calculated_text, "confidence": 90 if stated_total != calculated else 98, "corrected": True}
    if stated_total is None:
        parsed_fields[check_key] = {"value": missing_message, "confidence": 98, "corrected": True}
    elif stated_total == calculated:
        parsed_fields[check_key] = {"value": "klopt", "confidence": 98, "corrected": True}
    else:
        parsed_fields[check_key] = {
            "value": f"bijlage {_format_decimal(stated_total)}, som {_format_decimal(calculated)}",
            "confidence": 60,
            "corrected": True,
        }
