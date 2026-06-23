from pathlib import Path, PurePosixPath
from uuid import uuid4
import zipfile
from io import BytesIO

from psycopg2.errors import ForeignKeyViolation
from psycopg2.extras import Json

from apps.dashboard.data_store import ensure_dashboard_tables
from apps.dashboard.openai_usage import record_openai_api_audit, record_openai_usage
from apps.dashboard.phone_match import find_candidate_by_phone
from apps.dashboard.timesheet_parser import parse_timesheet
from shared.db.connection import get_connection


UPLOAD_DIR = Path("runtime/uploads/timesheets")


COMPLETE_PERIOD_SOURCE_CHANNEL = "complete_payroll_period_import"
SUPPORTED_TIMESHEET_IMPORT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def replace_complete_period_import(source_channel: str = COMPLETE_PERIOD_SOURCE_CHANNEL) -> int:
    ensure_dashboard_tables()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM project_time_bookings b
                USING whatsapp_timesheet_inbox w
                WHERE b.timesheet_inbox_id = w.id
                  AND w.source_channel = %s;
                """,
                (source_channel,),
            )
            cursor.execute(
                """
                UPDATE whatsapp_timesheet_inbox
                SET deleted_at = NOW(),
                    archived_at = NOW(),
                    updated_at = NOW()
                WHERE source_channel = %s
                  AND deleted_at IS NULL;
                """,
                (source_channel,),
            )
            replaced = cursor.rowcount
        conn.commit()
    return replaced


def import_complete_period_timesheets(
    uploads: list[tuple[str, bytes]],
    source_channel: str = COMPLETE_PERIOD_SOURCE_CHANNEL,
    replace_existing: bool = True,
    allow_openai: bool = False,
) -> dict:
    replaced = replace_complete_period_import(source_channel) if replace_existing else 0
    imported_ids: list[int] = []
    skipped: list[str] = []

    for filename, content in uploads:
        try:
            documents = list(_iter_import_documents(filename, content))
        except zipfile.BadZipFile:
            skipped.append(f"{filename}: zip niet leesbaar")
            continue
        except Exception as exc:
            skipped.append(f"{filename}: {type(exc).__name__}")
            continue

        for item_name, item_content in documents:
            try:
                record_id = save_timesheet_upload(
                    content=item_content,
                    filename=item_name,
                    sender_name="Complete loonperiode",
                    sender_phone="testset",
                    source_channel=source_channel,
                    allow_openai=allow_openai,
                )
                imported_ids.append(record_id)
            except Exception as exc:
                skipped.append(f"{item_name}: {type(exc).__name__}")
        if not _is_supported_archive_or_document(filename):
            skipped.append(f"{filename}: niet ondersteund")
        elif not documents:
            skipped.append(f"{filename}: geen ondersteunde urenbriefjes")

    return {
        "replaced": replaced,
        "imported": len(imported_ids),
        "imported_ids": imported_ids,
        "skipped": skipped,
    }


def _iter_import_documents(filename: str, content: bytes):
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        with zipfile.ZipFile(BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                entry_name = PurePosixPath(info.filename).name
                if Path(entry_name).suffix.lower() not in SUPPORTED_TIMESHEET_IMPORT_EXTENSIONS:
                    continue
                yield f"{Path(filename).stem}/{entry_name}", archive.read(info)
        return
    if suffix in SUPPORTED_TIMESHEET_IMPORT_EXTENSIONS:
        yield Path(filename).name, content


def _is_supported_archive_or_document(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix == ".zip" or suffix in SUPPORTED_TIMESHEET_IMPORT_EXTENSIONS


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

    def insert_upload(cursor, relation_id, candidate_name, upload_status):
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                upload_status,
                relation_id,
                candidate_name,
                parsed["employee_name"] or candidate_name,
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
        return cursor.fetchone()[0]

    with get_connection() as conn:
        try:
            with conn.cursor() as cursor:
                record_id = insert_upload(cursor, matched_relation_id, matched_candidate_name, status)
        except ForeignKeyViolation:
            conn.rollback()
            matched_relation_id = None
            matched_candidate_name = None
            status = "te_controleren"
            with conn.cursor() as cursor:
                record_id = insert_upload(cursor, None, None, status)
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
