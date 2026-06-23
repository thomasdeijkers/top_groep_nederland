from pathlib import Path
from uuid import uuid4

from psycopg2.extras import Json

from apps.dashboard.data_store import ensure_dashboard_tables
from apps.dashboard.openai_usage import record_openai_api_audit, record_openai_usage
from apps.dashboard.phone_match import find_candidate_by_phone
from apps.dashboard.timesheet_parser import parse_timesheet
from shared.db.connection import get_connection


UPLOAD_DIR = Path("runtime/uploads/timesheets")


def _match_candidate(sender_phone: str, parsed: dict) -> dict | None:
    parsed_phone = parsed.get("parsed_fields", {}).get("employee_phone", {}).get("value", "")
    if str(parsed_phone or "").strip():
        return find_candidate_by_phone(parsed_phone)
    return find_candidate_by_phone(sender_phone)


def save_timesheet_upload(
    content: bytes,
    filename: str,
    sender_name: str,
    sender_phone: str,
    source_channel: str = "manual_upload",
    allow_openai: bool = False,
) -> int:
    ensure_dashboard_tables()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid4().hex}_{Path(filename).name}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(content)

    parsed = parse_timesheet(content, filename, allow_openai=allow_openai)
    matched_candidate = _match_candidate(sender_phone, parsed)
    matched_relation_id = matched_candidate["id"] if matched_candidate else None
    matched_candidate_name = matched_candidate["name"] if matched_candidate else None
    parsed_phone = parsed.get("parsed_fields", {}).get("employee_phone", {}).get("value", "")
    stored_sender_phone = sender_phone.strip() or str(parsed_phone or "").strip() or "onbekend"
    status = "gematcht" if matched_candidate else "te_controleren"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO whatsapp_timesheet_inbox (
                    sender_name,
                    sender_phone,
                    message_text,
                    media_filename,
                    media_path,
                    parse_source,
                    source_channel,
                    status,
                    matched_relation_id,
                    matched_candidate_id,
                    matched_candidate_name,
                    employee_name,
                    employee_address,
                    employee_postal_code,
                    employee_city,
                    principal_name,
                    project_name,
                    work_date,
                    hours,
                    break_minutes,
                    parsed_fields,
                    overall_confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    sender_name.strip() or None,
                    stored_sender_phone,
                    parsed["message_text"],
                    filename,
                    str(file_path),
                    parsed.get("parse_source", "manual_upload"),
                    source_channel,
                    status,
                    matched_relation_id,
                    None,
                    matched_candidate_name,
                    parsed["employee_name"] or matched_candidate_name,
                    parsed["employee_address"],
                    parsed["employee_postal_code"],
                    parsed["employee_city"],
                    parsed["principal_name"],
                    parsed["project_name"],
                    parsed["work_date"],
                    parsed["hours"],
                    parsed["break_minutes"],
                    Json(parsed["parsed_fields"]),
                    parsed["overall_confidence"],
                ),
            )
            record_id = cursor.fetchone()[0]
        conn.commit()

    if parsed.get("openai_usage"):
        record_openai_usage("whatsapp_timesheet", record_id, parsed.get("model", "gpt-4.1-mini"), parsed["openai_usage"])
    if parsed.get("openai_api_audit"):
        audit = parsed["openai_api_audit"]
        record_openai_api_audit(
            "whatsapp_timesheet",
            record_id,
            audit.get("model", parsed.get("model", "gpt-4.1-mini")),
            audit.get("endpoint", ""),
            audit.get("request_payload") or {},
            audit.get("response_payload") or {},
            audit.get("status_code"),
            context={"purpose": "timesheet_ocr", "relation_id": matched_relation_id, "timesheet_inbox_id": record_id},
        )

    return record_id


def reparse_timesheet_upload(timesheet_id: int, allow_openai: bool = True) -> None:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT media_path, media_filename, sender_phone
                FROM whatsapp_timesheet_inbox
                WHERE id = %s
                  AND deleted_at IS NULL;
                """,
                (timesheet_id,),
            )
            row = cursor.fetchone()
    if not row:
        return

    media_path, media_filename, sender_phone = row
    file_path = Path(media_path)
    if not file_path.exists():
        return

    parsed = parse_timesheet(file_path.read_bytes(), media_filename or file_path.name, allow_openai=allow_openai)
    matched_candidate = _match_candidate(sender_phone, parsed)
    matched_relation_id = matched_candidate["id"] if matched_candidate else None
    matched_candidate_name = matched_candidate["name"] if matched_candidate else None
    status = "gematcht" if matched_candidate else "te_controleren"

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET message_text = %s,
                    parse_source = %s,
                    status = %s,
                    matched_relation_id = %s,
                    matched_candidate_name = %s,
                    employee_name = %s,
                    employee_address = %s,
                    employee_postal_code = %s,
                    employee_city = %s,
                    principal_name = %s,
                    project_name = %s,
                    work_date = %s,
                    hours = %s,
                    break_minutes = %s,
                    parsed_fields = %s,
                    overall_confidence = %s,
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (
                    parsed["message_text"],
                    parsed.get("parse_source", "manual_upload"),
                    status,
                    matched_relation_id,
                    matched_candidate_name,
                    parsed["employee_name"] or matched_candidate_name,
                    parsed["employee_address"],
                    parsed["employee_postal_code"],
                    parsed["employee_city"],
                    parsed["principal_name"],
                    parsed["project_name"],
                    parsed["work_date"],
                    parsed["hours"],
                    parsed["break_minutes"],
                    Json(parsed["parsed_fields"]),
                    parsed["overall_confidence"],
                    timesheet_id,
                ),
            )
        conn.commit()

    if parsed.get("openai_usage"):
        record_openai_usage("whatsapp_timesheet_reparse", timesheet_id, parsed.get("model", "gpt-4.1-mini"), parsed["openai_usage"])
    if parsed.get("openai_api_audit"):
        audit = parsed["openai_api_audit"]
        record_openai_api_audit(
            "whatsapp_timesheet_reparse",
            timesheet_id,
            audit.get("model", parsed.get("model", "gpt-4.1-mini")),
            audit.get("endpoint", ""),
            audit.get("request_payload") or {},
            audit.get("response_payload") or {},
            audit.get("status_code"),
            context={"purpose": "timesheet_ocr", "relation_id": matched_relation_id, "timesheet_inbox_id": timesheet_id},
        )
