from psycopg2.extras import Json
from decimal import Decimal
from datetime import datetime

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


class TimesheetValidationError(ValueError):
    pass


def save_field_corrections(
    timesheet_id: int,
    corrections: dict[str, str],
    matched_relation_id: int | None = None,
    clear_candidate_match: bool = False,
) -> None:
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
                if corrected_value == original_value:
                    continue
                parsed_fields[field_key] = {
                    "value": corrected_value,
                    "confidence": 98 if corrected_value else 0,
                    "corrected": True,
                    "verified": True,
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
                        "verified": True,
                    }
                    if matched_candidate_phone:
                        parsed_fields["employee_phone"] = {
                            "value": matched_candidate_phone,
                            "confidence": 98,
                            "corrected": True,
                            "verified": True,
                        }

            _apply_absence_code_to_day_codes(parsed_fields)
            _recalculate_total_checks(parsed_fields, original_totals)
            materialized_work_date = _date_from_fields(parsed_fields)
            materialized_hours = _decimal_or_none((parsed_fields.get("total_hours") or {}).get("value"))
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET parsed_fields = %s,
                    matched_relation_id = CASE WHEN %s THEN NULL ELSE COALESCE(%s, matched_relation_id) END,
                    matched_candidate_name = CASE WHEN %s THEN NULL ELSE COALESCE(%s, matched_candidate_name) END,
                    employee_name = COALESCE(%s, NULLIF(%s, ''), employee_name),
                    sender_phone = COALESCE(%s, NULLIF(%s, ''), sender_phone),
                    work_date = COALESCE(%s, work_date),
                    hours = COALESCE(%s, hours),
                    overall_confidence = LEAST(98, GREATEST(COALESCE(overall_confidence, 0), 80)),
                    status = 'goed_te_keuren',
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (
                    Json(parsed_fields),
                    clear_candidate_match,
                    matched_relation_id,
                    clear_candidate_match,
                    matched_candidate_name,
                    matched_candidate_name,
                    corrections.get("employee_name", ""),
                    matched_candidate_phone,
                    corrections.get("employee_phone", ""),
                    materialized_work_date,
                    materialized_hours,
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
                SELECT w.matched_relation_id,
                       w.work_date,
                       w.hours,
                       w.parsed_fields,
                       COALESCE(r.name, w.employee_name, w.matched_candidate_name, 'Onbekend') AS employee_name,
                       COALESCE(w.source_channel, 'dashboard') AS source_channel,
                       COALESCE(w.parse_source, 'manual') AS parse_source
                FROM whatsapp_timesheet_inbox w
                LEFT JOIN relations r ON r.id = w.matched_relation_id
                WHERE w.id = %s;
                """,
                (timesheet_id,),
            )
            row = cursor.fetchone()
            if not row:
                return

            relation_id, work_date, hours, parsed_fields, employee_name, source_channel, parse_source = row
            if not relation_id:
                raise TimesheetValidationError("Koppel eerst een kandidaat voordat je dit urenbriefje valideert.")
            cursor.execute(
                """
                SELECT 1
                FROM relations
                WHERE id = %s
                  AND relation_type = 'candidate'
                  AND archived_at IS NULL;
                """,
                (relation_id,),
            )
            if not cursor.fetchone():
                raise TimesheetValidationError("De gekoppelde kandidaat bestaat niet meer of is gearchiveerd.")
            parsed_fields = parsed_fields or {}
            _recalculate_total_checks(parsed_fields)
            work_date = _date_from_fields(parsed_fields) or work_date
            if not work_date:
                raise TimesheetValidationError("Vul eerst een werkdatum in zodat de juiste loonperiode bepaald kan worden.")
            hours = _decimal_or_none((parsed_fields.get("total_hours") or {}).get("value")) or hours or _hours_from_fields(parsed_fields)
            payroll_cao_setting_id = _project_cao_setting_id(cursor, project_id)
            payroll_period = _payroll_period_context(cursor, work_date)
            if not payroll_period:
                raise TimesheetValidationError("Geen loonperiode gevonden voor de werkdatum van dit urenbriefje.")
            payroll_period_id, payroll_period_week_id, week_number, period_number, period_year = payroll_period
            arrangement_id = _arrangement_id_for_period(cursor, relation_id, period_year, period_number)

            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET selected_principal_id = %s,
                    selected_project_id = %s,
                    parsed_fields = %s,
                    work_date = COALESCE(%s, work_date),
                    hours = COALESCE(%s, hours),
                    status = 'loon_te_berekenen',
                    validated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (principal_id, project_id, Json(parsed_fields), work_date, hours, timesheet_id),
            )
            cursor.execute(
                """
                DELETE FROM project_time_bookings
                WHERE timesheet_inbox_id = %s;
                """,
                (timesheet_id,),
            )
            cursor.execute(
                """
                INSERT INTO project_time_bookings (
                    timesheet_inbox_id, relation_id, principal_id, project_id,
                    payroll_cao_setting_id, payroll_period_id, work_date, hours, status, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'loon_te_berekenen', NOW())
                RETURNING id;
                """,
                (
                    timesheet_id,
                    relation_id,
                    principal_id,
                    project_id,
                    payroll_cao_setting_id,
                    payroll_period_id,
                    work_date,
                    hours,
                ),
            )
            booking_id = cursor.fetchone()[0]
            week_input_id = _upsert_payroll_week_input(
                cursor,
                payroll_period_id=payroll_period_id,
                payroll_period_week_id=payroll_period_week_id,
                relation_id=relation_id,
                arrangement_id=arrangement_id,
                timesheet_id=timesheet_id,
                week_number=week_number,
                employee_name=employee_name,
                work_date=work_date,
                source_channel=source_channel,
                parse_source=parse_source,
                status="loon_te_berekenen",
                worked_hours=hours,
                total_km=_total_km_from_fields(parsed_fields),
                parsed_fields=parsed_fields,
            )
            _replace_payroll_week_input_days(cursor, week_input_id, parsed_fields)
            _replace_payroll_week_input_project(
                cursor,
                week_input_id=week_input_id,
                booking_id=booking_id,
                principal_id=principal_id,
                project_id=project_id,
                work_date=work_date,
                hours=hours,
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


def _payroll_period_context(cursor, work_date):
    cursor.execute(
        """
        SELECT p.id,
               w.id,
               w.week_number,
               p.period_number,
               p.year
        FROM payroll_periods p
        JOIN payroll_period_weeks w
            ON w.payroll_period_id = p.id
           AND %s BETWEEN w.start_date AND w.end_date
        WHERE %s BETWEEN p.start_date AND p.end_date
        ORDER BY p.start_date DESC, w.week_index DESC
        LIMIT 1;
        """,
        (work_date, work_date),
    )
    return cursor.fetchone()


def _arrangement_id_for_period(cursor, relation_id: int, year: int, period_number: int):
    cursor.execute(
        """
        SELECT id
        FROM payroll_employee_arrangements
        WHERE relation_id = %s
          AND COALESCE(status, 'active') <> 'archief'
          AND (
              valid_from_year < %s
              OR (valid_from_year = %s AND valid_from_period_number <= %s)
          )
        ORDER BY valid_from_year DESC, valid_from_period_number DESC, id DESC
        LIMIT 1;
        """,
        (relation_id, year, year, period_number),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _upsert_payroll_week_input(
    cursor,
    *,
    payroll_period_id: int,
    payroll_period_week_id: int,
    relation_id: int,
    arrangement_id: int | None,
    timesheet_id: int,
    week_number: int,
    employee_name: str,
    work_date,
    source_channel: str,
    parse_source: str,
    status: str,
    worked_hours,
    total_km,
    parsed_fields: dict,
) -> int:
    cursor.execute(
        """
        INSERT INTO payroll_week_inputs (
            payroll_period_id, payroll_period_week_id, relation_id, arrangement_id,
            timesheet_inbox_id, week_number, employee_name, work_date, source_channel,
            parse_source, status, worked_hours, total_km, day_codes, raw_fields,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, 0), COALESCE(%s, 0), %s, %s, NOW(), NOW())
        ON CONFLICT (timesheet_inbox_id) WHERE timesheet_inbox_id IS NOT NULL
        DO UPDATE SET
            payroll_period_id = EXCLUDED.payroll_period_id,
            payroll_period_week_id = EXCLUDED.payroll_period_week_id,
            relation_id = EXCLUDED.relation_id,
            arrangement_id = EXCLUDED.arrangement_id,
            week_number = EXCLUDED.week_number,
            employee_name = EXCLUDED.employee_name,
            work_date = EXCLUDED.work_date,
            source_channel = EXCLUDED.source_channel,
            parse_source = EXCLUDED.parse_source,
            status = EXCLUDED.status,
            worked_hours = EXCLUDED.worked_hours,
            total_km = EXCLUDED.total_km,
            day_codes = EXCLUDED.day_codes,
            raw_fields = EXCLUDED.raw_fields,
            updated_at = NOW()
        RETURNING id;
        """,
        (
            payroll_period_id,
            payroll_period_week_id,
            relation_id,
            arrangement_id,
            timesheet_id,
            week_number,
            employee_name or "Onbekend",
            work_date,
            source_channel or "dashboard",
            parse_source or "manual",
            status,
            worked_hours,
            total_km,
            Json(_day_codes_from_fields(parsed_fields)),
            Json(parsed_fields),
        ),
    )
    return cursor.fetchone()[0]


def _replace_payroll_week_input_days(cursor, week_input_id: int, parsed_fields: dict) -> None:
    cursor.execute("DELETE FROM payroll_week_input_days WHERE payroll_week_input_id = %s;", (week_input_id,))
    for index, day_name, hours_key, km_key, code_key in (
        (1, "maandag", "monday_hours", "monday_km", "monday_code"),
        (2, "dinsdag", "tuesday_hours", "tuesday_km", "tuesday_code"),
        (3, "woensdag", "wednesday_hours", "wednesday_km", "wednesday_code"),
        (4, "donderdag", "thursday_hours", "thursday_km", "thursday_code"),
        (5, "vrijdag", "friday_hours", "friday_km", "friday_code"),
        (6, "zaterdag", "saturday_hours", "saturday_km", "saturday_code"),
        (7, "zondag", "sunday_hours", "sunday_km", "sunday_code"),
    ):
        cursor.execute(
            """
            INSERT INTO payroll_week_input_days (
                payroll_week_input_id, day_index, day_name, hours, km, day_code, source, created_at, updated_at
            )
            VALUES (%s, %s, %s, COALESCE(%s, 0), COALESCE(%s, 0), %s, 'parsed_fields', NOW(), NOW());
            """,
            (
                week_input_id,
                index,
                day_name,
                _decimal_or_none((parsed_fields.get(hours_key) or {}).get("value")),
                _decimal_or_none((parsed_fields.get(km_key) or {}).get("value")),
                str((parsed_fields.get(code_key) or {}).get("value") or "").strip() or None,
            ),
        )


def _replace_payroll_week_input_project(
    cursor,
    *,
    week_input_id: int,
    booking_id: int,
    principal_id: int | None,
    project_id: int | None,
    work_date,
    hours,
) -> None:
    cursor.execute("DELETE FROM payroll_week_input_projects WHERE payroll_week_input_id = %s;", (week_input_id,))
    cursor.execute(
        """
        INSERT INTO payroll_week_input_projects (
            payroll_week_input_id, project_time_booking_id, principal_id, project_id,
            work_date, hours, status, source, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, COALESCE(%s, 0), 'loon_te_berekenen', 'project_time_bookings', NOW(), NOW());
        """,
        (week_input_id, booking_id, principal_id, project_id, work_date, hours),
    )


def _day_codes_from_fields(parsed_fields: dict) -> dict:
    return {
        "monday": str((parsed_fields.get("monday_code") or {}).get("value") or ""),
        "tuesday": str((parsed_fields.get("tuesday_code") or {}).get("value") or ""),
        "wednesday": str((parsed_fields.get("wednesday_code") or {}).get("value") or ""),
        "thursday": str((parsed_fields.get("thursday_code") or {}).get("value") or ""),
        "friday": str((parsed_fields.get("friday_code") or {}).get("value") or ""),
        "saturday": str((parsed_fields.get("saturday_code") or {}).get("value") or ""),
        "sunday": str((parsed_fields.get("sunday_code") or {}).get("value") or ""),
    }


def _total_km_from_fields(parsed_fields: dict):
    for key in ("total_km", "calculated_total_km"):
        value = _decimal_or_none((parsed_fields.get(key) or {}).get("value"))
        if value is not None:
            return value
    total = Decimal("0")
    for key in ("monday_km", "tuesday_km", "wednesday_km", "thursday_km", "friday_km", "saturday_km", "sunday_km"):
        total += _decimal_or_none((parsed_fields.get(key) or {}).get("value")) or Decimal("0")
    return total


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


def _date_from_fields(parsed_fields: dict):
    value = str((parsed_fields.get("date") or {}).get("value") or "").strip()
    if not value:
        return None
    for pattern in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
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
    current_total = _decimal_or_none((parsed_fields.get(total_key) or {}).get("value"))
    original_total = _decimal_or_none(original_total_value)
    stated_total = current_total if current_total is not None else original_total
    known_day_payloads = [
        parsed_fields.get(key) or {}
        for key in day_keys
        if _decimal_or_none((parsed_fields.get(key) or {}).get("value")) is not None
    ]
    all_days_verified = bool(known_day_payloads) and all(payload.get("verified") for payload in known_day_payloads)
    total_verified = bool((parsed_fields.get(total_key) or {}).get("verified"))
    verified_check = all_days_verified and total_verified
    calculated_confidence = 98 if all_days_verified else 60
    parsed_fields[calculated_key] = {
        "value": calculated_text,
        "confidence": calculated_confidence,
        "corrected": True,
        "verified": all_days_verified,
    }
    if stated_total is None:
        parsed_fields[total_key] = {
            "value": calculated_text,
            "confidence": calculated_confidence,
            "corrected": True,
            "verified": all_days_verified,
        }
        parsed_fields[check_key] = {
            "value": "klopt",
            "confidence": calculated_confidence,
            "corrected": True,
            "verified": all_days_verified,
        }
    elif stated_total == calculated:
        parsed_fields[total_key] = {
            "value": _format_decimal(stated_total),
            "confidence": 98 if total_verified else 60,
            "corrected": True,
            "verified": total_verified,
        }
        parsed_fields[check_key] = {
            "value": "klopt",
            "confidence": 98 if verified_check else 60,
            "corrected": True,
            "verified": verified_check,
        }
    else:
        existing_total = parsed_fields.get(total_key) or {}
        parsed_fields[total_key] = {
            "value": _format_decimal(stated_total),
            "confidence": min(int(existing_total.get("confidence", 0) or 0), 60),
            "corrected": True,
            "verified": total_verified,
        }
        parsed_fields[check_key] = {
            "value": f"bijlage {_format_decimal(stated_total)}, som {_format_decimal(calculated)}",
            "confidence": 60,
            "corrected": True,
            "verified": False,
        }
