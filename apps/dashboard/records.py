import json
from datetime import date, datetime, timedelta
from pathlib import Path
from decimal import Decimal

from psycopg2.extras import Json

from apps.dashboard.addressing import split_street_house_number
from apps.dashboard.data_store import ensure_dashboard_tables
from apps.dashboard.payroll_calculations import (
    build_payslip_sheet_rows,
    build_period_sheet_rows,
    build_workbook_tabs,
    default_calculation_rules,
    derived_period_total_rows,
    summarize_week_rows,
    summarize_workbook_tabs,
)
from shared.db.connection import get_connection


PAYROLL_PERIODS_PER_YEAR = 13


def _ensure_dashboard_tables_for_read() -> None:
    try:
        ensure_dashboard_tables()
    except Exception as exc:
        print(f"DASHBOARD_SCHEMA_ENSURE_READ_WARNING {type(exc).__name__}: {exc}")


def ensure_visible_demo_payroll_data() -> None:
    """Keep the test dashboard usable when the connected database is empty."""
    migrations = (
        Path("migrations/039_full_year_test_payroll.sql"),
        Path("migrations/041_dashboard_demo_payroll.sql"),
        Path("migrations/033_payroll_week_inputs.sql"),
        Path("migrations/034_payroll_week_results.sql"),
        Path("migrations/035_payroll_period_settlements.sql"),
    )
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM relations WHERE relation_type = 'candidate' AND archived_at IS NULL) AS candidate_count,
                        (SELECT COUNT(*) FROM relations WHERE relation_type = 'principal' AND archived_at IS NULL) AS principal_count,
                        (SELECT COUNT(*) FROM payroll_periods WHERE year = 2026) AS period_count,
                        (
                            SELECT COUNT(*)
                            FROM whatsapp_timesheet_inbox
                            WHERE deleted_at IS NULL
                              AND archived_at IS NULL
                              AND LOWER(REPLACE(COALESCE(status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                        ) AS payroll_timesheet_count;
                    """
                )
                candidate_count, principal_count, period_count, payroll_timesheet_count = cursor.fetchone()
                if candidate_count and principal_count and period_count and payroll_timesheet_count:
                    return
                for migration in migrations:
                    try:
                        cursor.execute(migration.read_text(encoding="utf-8"))
                        conn.commit()
                    except Exception as migration_exc:
                        conn.rollback()
                        print(f"DASHBOARD_DEMO_PAYROLL_SEED_STEP_ERROR {migration.name}: {type(migration_exc).__name__}: {migration_exc}")
    except Exception as exc:
        print(f"DASHBOARD_DEMO_PAYROLL_SEED_ERROR {type(exc).__name__}: {exc}")

def get_overview_data() -> dict:
    try:
        _ensure_dashboard_tables_for_read()
        ensure_visible_demo_payroll_data()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                counts = {}
                for table_name in ("vacancies", "tickets"):
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    counts[table_name] = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT LOWER(relation_type), COUNT(*)
                    FROM relations
                    WHERE archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    GROUP BY LOWER(relation_type);
                    """
                )
                relation_counts = {row[0]: row[1] for row in cursor.fetchall()}
                counts["candidates"] = relation_counts.get("candidate", 0)
                counts["principals"] = relation_counts.get("principal", 0)
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM whatsapp_timesheet_inbox
                    WHERE deleted_at IS NULL
                      AND archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) IN (
                          'nieuw',
                          'geupload',
                          'uploaded',
                          'gematcht',
                          'matched',
                          'te_controleren',
                          'controle',
                          'goed_te_keuren',
                          'approval',
                          'akkoord_nodig',
                          'loon_te_berekenen'
                      );
                    """
                )
                counts["whatsapp_timesheet_inbox"] = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT
                        CASE relation_type
                            WHEN 'candidate' THEN 'Kandidaat'
                            ELSE 'Opdrachtgever'
                        END AS type,
                        name,
                        COALESCE(status, ''),
                        updated_at
                    FROM relations
                    WHERE archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    UNION ALL
                    SELECT 'Vacature' AS type, title, COALESCE(status, ''), updated_at
                    FROM vacancies
                    UNION ALL
                    SELECT 'Ticket' AS type, title, COALESCE(status, ''), updated_at
                    FROM tickets
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 20;
                    """
                )
                recent = [
                    {
                        "type": row[0],
                        "name": row[1],
                        "status": row[2] or "-",
                        "updated_at": row[3].strftime("%d-%m-%Y %H:%M") if row[3] else "-",
                    }
                    for row in cursor.fetchall()
                ]

                cursor.execute(
                    """
                    SELECT status, COUNT(*)
                    FROM whatsapp_timesheet_inbox
                    WHERE deleted_at IS NULL
                      AND archived_at IS NULL
                    GROUP BY status;
                    """
                )
                whatsapp_statuses = {row[0]: row[1] for row in cursor.fetchall()}
                weekly_hours_yoy = _weekly_hours_yoy(cursor)

        return {
            "counts": counts,
            "recent": recent,
            "whatsapp_workflow": _whatsapp_workflow(whatsapp_statuses),
            "weekly_hours_yoy": weekly_hours_yoy or _demo_weekly_hours_yoy(),
        }
    except Exception:
        return {
            "counts": {
                "candidates": 0,
                "principals": 0,
                "vacancies": 0,
                "tickets": 0,
                "whatsapp_timesheet_inbox": 0,
            },
            "recent": [],
            "whatsapp_workflow": _whatsapp_workflow({}),
            "weekly_hours_yoy": _demo_weekly_hours_yoy(),
        }


def _weekly_hours_yoy(cursor, weeks_back: int = 8) -> list[dict]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week_starts = [monday - timedelta(days=7 * index) for index in range(weeks_back - 1, -1, -1)]
    current_start = week_starts[0]
    current_end = week_starts[-1] + timedelta(days=6)
    previous_start = current_start.replace(year=current_start.year - 1)
    previous_end = current_end.replace(year=current_end.year - 1)
    cursor.execute(
        """
        SELECT EXTRACT(ISOYEAR FROM work_date)::int AS iso_year,
               EXTRACT(WEEK FROM work_date)::int AS iso_week,
               COALESCE(SUM(hours), 0) AS total_hours
        FROM project_time_bookings
        WHERE work_date BETWEEN %s AND %s
           OR work_date BETWEEN %s AND %s
        GROUP BY iso_year, iso_week;
        """,
        (current_start, current_end, previous_start, previous_end),
    )
    totals = {(row[0], row[1]): Decimal(str(row[2] or 0)) for row in cursor.fetchall()}
    current_year = today.isocalendar().year
    previous_year = current_year - 1
    week_numbers = [start.isocalendar().week for start in week_starts]
    cursor.execute(
        """
        SELECT DISTINCT ON (pw.week_number)
               pw.week_number,
               p.id
        FROM payroll_period_weeks pw
        JOIN payroll_periods p ON p.id = pw.payroll_period_id
        WHERE p.year = %s
          AND pw.week_number = ANY(%s)
        ORDER BY pw.week_number, p.start_date DESC, p.id DESC;
        """,
        (current_year, week_numbers),
    )
    period_by_week = {row[0]: row[1] for row in cursor.fetchall()}
    max_hours = max(
        [Decimal("1")]
        + [totals.get((start.isocalendar().year, start.isocalendar().week), Decimal("0")) for start in week_starts]
        + [totals.get((previous_year, start.isocalendar().week), Decimal("0")) for start in week_starts]
    )
    rows = []
    for start in week_starts:
        week_number = start.isocalendar().week
        current_hours = totals.get((start.isocalendar().year, week_number), Decimal("0"))
        previous_hours = totals.get((previous_year, week_number), Decimal("0"))
        if previous_hours:
            yoy = ((current_hours - previous_hours) / previous_hours * Decimal("100")).quantize(Decimal("0.01"))
        elif current_hours:
            yoy = Decimal("100")
        else:
            yoy = Decimal("0")
        rows.append(
            {
                "label": f"WK{week_number}",
                "date_label": start.strftime("%d-%m"),
                "href": f"/dashboard/periods?period={period_by_week[week_number]}&week=WK{week_number}#periode-verloning" if week_number in period_by_week else "/dashboard/periods#periodes",
                "is_demo": False,
                "source_label": "Boekingen",
                "current_year": current_year,
                "previous_year": previous_year,
                "current_hours": _format_number(current_hours),
                "previous_hours": _format_number(previous_hours),
                "current_height": int((current_hours / max_hours) * 100) if max_hours else 0,
                "previous_height": int((previous_hours / max_hours) * 100) if max_hours else 0,
                "yoy": f"{'+' if yoy > 0 else ''}{str(yoy).replace('.', ',')}%",
                "yoy_positive": yoy >= 0,
            }
        )
    has_hours = any(row["current_hours"] != "0" or row["previous_hours"] != "0" for row in rows)
    return rows if has_hours else []


def _demo_weekly_hours_yoy() -> list[dict]:
    demo = [
        ("WK19", 186, 248),
        ("WK20", 379, 538),
        ("WK21", 489, 271),
        ("WK22", 371, 369),
        ("WK23", 455, 696),
        ("WK24", 490, 462),
        ("WK25", 327, 662),
        ("WK26", 87, 248),
    ]

    max_hours = max(max(previous, current) for _, previous, current in demo)
    rows = []
    for label, previous, current in demo:
        yoy = ((Decimal(current) - Decimal(previous)) / Decimal(previous) * Decimal("100")).quantize(Decimal("0.01"))
        rows.append(
            {
                "label": label,
                "date_label": label,
                "href": "/dashboard/periods#periodes",
                "is_demo": True,
                "source_label": "Demo",
                "current_year": date.today().year,
                "previous_year": date.today().year - 1,
                "current_hours": _format_number(current),
                "previous_hours": _format_number(previous),
                "current_height": int(current / max_hours * 100),
                "previous_height": int(previous / max_hours * 100),
                "yoy": f"{'+' if yoy > 0 else ''}{str(yoy).replace('.', ',')}%",
                "yoy_positive": yoy >= 0,
            }
        )
    return rows


def log_audit_event(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    entity_label: str = "",
    description: str = "",
    status: str = "",
    metadata: dict | None = None,
    actor_name: str = "Admin",
) -> None:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (
                        actor_name,
                        action,
                        entity_type,
                        entity_id,
                        entity_label,
                        description,
                        status,
                        metadata,
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    (
                        actor_name or "Admin",
                        action,
                        entity_type,
                        entity_id,
                        entity_label or "",
                        description or "",
                        status or "",
                        Json(metadata or {}),
                    ),
                )
            conn.commit()
    except Exception:
        return


def list_audit_events(limit: int = 25, entity_type: str = "", entity_id: int | None = None) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                filters = []
                params: list = []
                if entity_type:
                    filters.append("entity_type = %s")
                    params.append(entity_type)
                if entity_id:
                    filters.append("entity_id = %s")
                    params.append(entity_id)
                where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
                cursor.execute(
                    f"""
                    SELECT id,
                           actor_name,
                           action,
                           entity_type,
                           entity_id,
                           entity_label,
                           description,
                           status,
                           metadata,
                           created_at
                    FROM audit_events
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (*params, limit),
                )
                rows = [
                    {
                        "id": row[0],
                        "user": row[1] or "Admin",
                        "title": row[2],
                        "entity_type": row[3],
                        "entity_id": row[4],
                        "entity_label": row[5] or "",
                        "entity_display": row[5] or f"{row[3] or 'record'} {row[4] or ''}".strip(),
                        "meta": row[5] or row[3],
                        "detail": row[6] or "",
                        "status": row[7] or row[3],
                        "metadata": row[8] or {},
                        "metadata_summary": _audit_metadata_summary(row[8] or {}),
                        "privacy_summary": "",
                        "time": row[9].strftime("%d-%m-%Y %H:%M") if row[9] else "-",
                        "date": row[9].strftime("%d-%m-%Y") if row[9] else "-",
                        "clock": row[9].strftime("%H:%M") if row[9] else "-",
                    }
                    for row in cursor.fetchall()
                ]
                try:
                    _enrich_audit_events(cursor, rows)
                except Exception:
                    pass
                return rows
    except Exception:
        return []


def _enrich_audit_events(cursor, rows: list[dict]) -> None:
    if not rows:
        return
    timesheet_ids = [row["entity_id"] for row in rows if row.get("entity_type") == "urenbriefje" and row.get("entity_id")]
    relation_ids = [
        row["entity_id"]
        for row in rows
        if row.get("entity_type") in {"relatie", "candidate", "principal"} and row.get("entity_id")
    ]
    timesheets = _audit_timesheet_context(cursor, timesheet_ids)
    relations = _audit_relation_context(cursor, relation_ids)
    for row in rows:
        if row.get("entity_type") == "urenbriefje":
            context = timesheets.get(row.get("entity_id"))
            if context:
                row["entity_display"] = context["display"]
                row["detail"] = _audit_detail_with_context(row["detail"], context["summary"])
                row["metadata_summary"] = _combine_audit_summary(row["metadata_summary"], context["metadata"])
                row["privacy_summary"] = context.get("privacy", "")
        elif row.get("entity_type") in {"relatie", "candidate", "principal"}:
            context = relations.get(row.get("entity_id"))
            if context:
                row["entity_display"] = context["display"]
                row["detail"] = _audit_detail_with_context(row["detail"], context["summary"])
                row["metadata_summary"] = _combine_audit_summary(row["metadata_summary"], context["metadata"])
                row["privacy_summary"] = context.get("privacy", "")


def _audit_timesheet_context(cursor, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    cursor.execute(
        """
        SELECT id,
               COALESCE(employee_name, matched_candidate_name, sender_name, '') AS employee_name,
               COALESCE(sender_phone, '') AS sender_phone,
               COALESCE(project_name, '') AS project_name,
               COALESCE(principal_name, '') AS principal_name,
               week_number,
               work_date,
               hours,
               COALESCE(media_filename, '') AS media_filename,
               COALESCE(status, '') AS status,
               COALESCE(parse_source, '') AS parse_source,
               overall_confidence,
               COALESCE(source_channel, '') AS source_channel,
               COALESCE(parsed_fields, '{}'::jsonb) AS parsed_fields,
               matched_relation_id,
               selected_principal_id,
               selected_project_id
        FROM whatsapp_timesheet_inbox
        WHERE id = ANY(%s);
        """,
        (ids,),
    )
    contexts = {}
    for row in cursor.fetchall():
        bits = [bit for bit in [row[1], row[3], f"week {row[5]}" if row[5] else "", row[8]] if bit]
        display = f"Urenbriefje #{row[0]}"
        if bits:
            display = f"{display} · {' · '.join(bits[:3])}"
        summary_parts = []
        if row[1]:
            summary_parts.append(f"werknemer {row[1]}")
        if row[3]:
            summary_parts.append(f"project {row[3]}")
        if row[4]:
            summary_parts.append(f"opdrachtgever {row[4]}")
        if row[7]:
            summary_parts.append(f"{_format_number(row[7])} uur")
        metadata_parts = []
        if row[2]:
            metadata_parts.append(f"telefoon: {row[2]}")
        if row[8]:
            metadata_parts.append(f"bestand: {row[8]}")
        if row[9]:
            metadata_parts.append(f"huidige status: {row[9]}")
        privacy_parts = [
            "AVG-context urenbriefje",
            f"- Urenbriefje ID: {row[0]}",
            f"- Bronkanaal: {row[12] or '-'}",
            f"- Parsebron: {row[10] or '-'}",
            f"- Bestand/document: {row[8] or '-'}",
            f"- Werknemer/afzender: {row[1] or '-'}",
            f"- Telefoonnummer: {row[2] or '-'}",
            f"- Opdrachtgever: {row[4] or '-'}",
            f"- Project/werk: {row[3] or '-'}",
            f"- Werkdatum: {row[6].strftime('%d-%m-%Y') if row[6] else '-'}",
            f"- Uren: {_format_number(row[7]) if row[7] else '-'}",
            f"- Status: {row[9] or '-'}",
            f"- Parserzekerheid: {int(row[11] or 0)}%",
            f"- Gekoppelde kandidaat/relatie ID: {row[14] or '-'}",
            f"- Geselecteerde opdrachtgever ID: {row[15] or '-'}",
            f"- Geselecteerd project ID: {row[16] or '-'}",
            f"- Ingevulde parsingvelden: {_filled_parsed_field_summary(row[13] or {})}",
            f"- ChatGPT betrokken: {'ja' if (row[10] or '').lower() == 'openai' else 'nee'}",
        ]
        contexts[row[0]] = {
            "display": display,
            "summary": ", ".join(summary_parts),
            "metadata": " | ".join(metadata_parts),
            "privacy": "\n".join(privacy_parts),
        }
    return contexts


def _audit_relation_context(cursor, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    cursor.execute(
        """
        SELECT id,
               relation_type,
               COALESCE(name, '') AS name,
               COALESCE(contact_name, '') AS contact_name,
               COALESCE(email, '') AS email,
               COALESCE(phone, '') AS phone,
               COALESCE(city, '') AS city,
               COALESCE(status, '') AS status,
               COALESCE(street, '') AS street,
               COALESCE(house_number, '') AS house_number,
               COALESCE(postal_code, '') AS postal_code,
               COALESCE(country, '') AS country,
               COALESCE(kvk_number, '') AS kvk_number,
               COALESCE(vat_number, '') AS vat_number
        FROM relations
        WHERE id = ANY(%s);
        """,
        (ids,),
    )
    contexts = {}
    for row in cursor.fetchall():
        relation_type = "Opdrachtgever" if row[1] == "principal" else "Kandidaat"
        display = f"{relation_type} #{row[0]}"
        if row[2]:
            display = f"{display} · {row[2]}"
        summary_parts = []
        if row[3]:
            summary_parts.append(f"contact {row[3]}")
        if row[6]:
            summary_parts.append(f"plaats {row[6]}")
        if row[7]:
            summary_parts.append(f"status {row[7]}")
        metadata_parts = []
        if row[4]:
            metadata_parts.append(f"e-mail: {row[4]}")
        if row[5]:
            metadata_parts.append(f"telefoon: {row[5]}")
        contexts[row[0]] = {
            "display": display,
            "summary": ", ".join(summary_parts),
            "metadata": " | ".join(metadata_parts),
            "privacy": "\n".join(
                [
                    "AVG-context relatie",
                    f"- Type: {relation_type}",
                    f"- Naam: {row[2] or '-'}",
                    f"- Contactpersoon: {row[3] or '-'}",
                    f"- E-mail: {row[4] or '-'}",
                    f"- Telefoon: {row[5] or '-'}",
                    f"- Adres: {' '.join(part for part in (row[8], row[9]) if part) or '-'}",
                    f"- Postcode/plaats: {' '.join(part for part in (row[10], row[6]) if part) or '-'}",
                    f"- Land: {row[11] or '-'}",
                    f"- KvK: {row[12] or '-'}",
                    f"- BTW: {row[13] or '-'}",
                    f"- Status: {row[7] or '-'}",
                ]
            ),
        }
    return contexts


def _audit_detail_with_context(detail: str, context: str) -> str:
    if not context:
        return detail
    if not detail:
        return context.capitalize() + "."
    return f"{detail} Betreft: {context}."


def _combine_audit_summary(summary: str, context: str) -> str:
    if not context:
        return summary
    if not summary or summary == "Geen extra metadata":
        return context
    return f"{summary} | {context}"


def _audit_metadata_summary(metadata) -> str:
    if not isinstance(metadata, dict) or not metadata:
        return "Geen extra metadata"
    parts = []
    for key, value in metadata.items():
        if value in (None, "", [], {}):
            continue
        label = str(key).replace("_", " ")
        parts.append(f"{label}: {value}")
        if len(parts) >= 4:
            break
    return " | ".join(parts) if parts else "Geen extra metadata"


def _filled_parsed_field_summary(fields: dict) -> str:
    if not isinstance(fields, dict) or not fields:
        return "geen parsed_fields opgeslagen"
    labels = {
        "employee_name": "werknemer",
        "employee_phone": "telefoon",
        "principal_name": "opdrachtgever",
        "project_name": "project",
        "work_name": "werk",
        "date": "datum",
        "week_number": "week",
        "total_hours": "uren totaal",
        "total_km": "km totaal",
        "signature": "handtekening",
        "client_signature": "handtekening opdrachtgever",
        "remarks": "opmerking",
    }
    filled = []
    for key, field in fields.items():
        value = field.get("value") if isinstance(field, dict) else field
        if value in (None, "", [], {}):
            continue
        label = labels.get(key, str(key).replace("_", " "))
        confidence = field.get("confidence") if isinstance(field, dict) else None
        suffix = f" ({confidence}%)" if confidence not in (None, "") else ""
        filled.append(f"{label}: {value}{suffix}")
    return "; ".join(filled[:18]) if filled else "geen ingevulde parsingvelden"


def _whatsapp_workflow(statuses: dict) -> list[dict]:
    definitions = [
        {
            "key": "te_controleren",
            "label": "Te controleren parsing",
            "description": "OCR/parsing onder controlegrens",
            "statuses": ("te_controleren", "controle", "Te controleren"),
        },
        {
            "key": "goed_te_keuren",
            "label": "Goed te keuren uren",
            "description": "Klaar voor akkoord",
            "statuses": ("goed_te_keuren", "approval", "akkoord_nodig"),
        },
        {
            "key": "loon_te_berekenen",
            "label": "Loon berekenen",
            "description": "Gevalideerd en geboekt op project",
            "statuses": ("loon_te_berekenen",),
        },
        {
            "key": "verwerkt",
            "label": "Loonadministratie",
            "description": "Doorgestuurd naar loonadministratie",
            "statuses": ("doorgestuurd_naar_loonadministratie", "verwerkt", "processed"),
        },
    ]
    return [
        {
            "key": item["key"],
            "label": item["label"],
            "description": item["description"],
            "count": sum(statuses.get(status, 0) for status in item["statuses"]),
        }
        for item in definitions
    ]


def get_timesheet_channel_tiles() -> list[dict]:
    labels = {
        "whatsapp": (
            "WhatsApp",
            "Automatische aanvoer via WhatsApp Business",
            "https://cdn.jsdelivr.net/npm/simple-icons@v11/icons/whatsapp.svg",
        ),
        "email": (
            "E-mail",
            "Urenbriefjes uit mailbox",
            "https://api.iconify.design/lucide:mail.svg",
        ),
        "server_folder": (
            "Servermap",
            "Bestanden uit bewaakte servermap",
            "https://api.iconify.design/lucide:folder-sync.svg",
        ),
        "manual_upload": (
            "Handmatige test",
            "Los uploaden voor live test",
            "https://api.iconify.design/lucide:upload-cloud.svg",
        ),
    }
    counts = {key: 0 for key in labels}
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT source_channel, COUNT(*)
                    FROM whatsapp_timesheet_inbox
                    WHERE deleted_at IS NULL
                    GROUP BY source_channel;
                    """
                )
                for source_channel, count in cursor.fetchall():
                    counts[source_channel or "manual_upload"] = count
    except Exception:
        pass

    return [
        {
            "key": key,
            "label": label,
            "description": description,
            "icon_url": icon_url,
            "count": counts.get(key, 0),
            "status": "Actief" if key == "manual_upload" else "Later",
            "target": "timesheet-processing",
        }
        for key, (label, description, icon_url) in labels.items()
    ]


def list_candidates(limit: int = 25, query: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                where_clause = ""
                if query:
                    where_clause = """
                    AND (
                       name ILIKE %s
                       OR email ILIKE %s
                       OR phone ILIKE %s
                       OR city ILIKE %s
                       OR status ILIKE %s
                    )
                    """
                    like_query = f"%{query}%"
                    params.extend([like_query] * 5)
                params.append(limit)
                cursor.execute(
                    f"""
                    SELECT id, name, email, phone, city, status, COALESCE(source, '')
                    FROM relations
                    WHERE relation_type = 'candidate'
                      AND archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    {where_clause}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                return [
                    {
                        "id": row[0],
                        "name": row[1],
                        "email": row[2] or "-",
                        "phone": row[3] or "-",
                        "city": row[4] or "-",
                        "status": row[5] or "Nog beoordelen",
                        "source": row[6] or "Import",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_relations(limit: int = 15, query: str = "", relation_type: str = "", status: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        ensure_visible_demo_payroll_data()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                filters = [
                    "archived_at IS NULL",
                    "LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')",
                ]
                if relation_type in {"candidate", "principal"}:
                    filters.append("relation_type = %s")
                    params.append(relation_type)
                if status:
                    filters.append("status = %s")
                    params.append(status)
                if query:
                    filters.append(
                        """
                    (
                       name ILIKE %s
                       OR contact_name ILIKE %s
                       OR email ILIKE %s
                       OR phone ILIKE %s
                       OR city ILIKE %s
                       OR status ILIKE %s
                       OR external_id ILIKE %s
                      )
                    """
                    )
                    like_query = f"%{query}%"
                    params.extend([like_query] * 7)
                params.append(limit)
                where_clause = "WHERE " + " AND ".join(filters)
                cursor.execute(
                    f"""
                    SELECT id, relation_type, name, contact_name, email, phone,
                           city, status, COALESCE(source, ''), photo_path,
                           street, house_number, house_number_addition, postal_code, country,
                           external_id, updated_at
                    FROM relations
                    {where_clause}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                rows = []
                for row in cursor.fetchall():
                    street, house_number, house_number_addition = split_street_house_number(row[10], row[11], row[12])
                    postal_code = row[13]
                    country = row[14]
                    required_fields = [
                        row[2],  # naam
                        row[5],  # telefoon
                        street,
                        house_number,
                        postal_code,
                        row[6],  # plaats
                    ]
                    completion_fields = [
                        row[2],
                        row[4],
                        row[5],
                        row[6],
                        row[7],
                        street,
                        house_number,
                        postal_code,
                        country,
                        row[15],
                    ]
                    if row[1] == "principal":
                        completion_fields.extend([row[3]])
                    filled_count = sum(1 for value in completion_fields if str(value or "").strip())
                    completion_total = len(completion_fields)
                    completion_percent = round((filled_count / completion_total) * 100) if completion_total else 0
                    has_required_details = all(str(value or "").strip() for value in required_fields)
                    if completion_percent > 75 and has_required_details:
                        completion_tone = "green"
                        completion_status = "Compleet"
                    elif completion_percent >= 50:
                        completion_tone = "orange"
                        completion_status = "Basis"
                    else:
                        completion_tone = "red"
                        completion_status = "Onvolledig"
                    rows.append({
                        "id": row[0],
                        "relation_type": row[1],
                        "type": "Opdrachtgever" if row[1] == "principal" else "Kandidaat",
                        "name": row[2] or "",
                        "contact": row[5] or "",
                        "email": row[4] or "",
                        "phone": row[5] or "",
                        "city": row[6] or "",
                        "status": row[7] or "",
                        "source": row[8] or "",
                        "has_photo": bool(row[9]),
                        "initials": _initials(row[2]),
                        "street": street,
                        "house_number": house_number,
                        "house_number_addition": house_number_addition,
                        "postal_code": row[13] or "",
                        "country": row[14] or "",
                        "external_id": row[15] or "",
                        "updated_at": row[16].strftime("%d-%m-%Y %H:%M") if row[16] else "",
                        "completion_percent": completion_percent,
                        "completion_label": f"{completion_percent}%",
                        "completion_status": completion_status,
                        "completion_tone": completion_tone,
                        "completion_required_complete": has_required_details,
                    })
                return rows
    except Exception:
        return []


def search_candidate_matches(query: str = "", limit: int = 40) -> list[dict]:
    search = str(query or "").strip()
    limit = max(1, min(int(limit or 40), 80))
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                where_relation = """
                    relation_type = 'candidate'
                    AND archived_at IS NULL
                    AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                """
                if search:
                    where_relation += """
                        AND (
                            name ILIKE %s
                            OR email ILIKE %s
                            OR phone ILIKE %s
                            OR city ILIKE %s
                            OR external_id ILIKE %s
                        )
                    """
                    like = f"%{search}%"
                    params.extend([like] * 5)
                params.append(limit)
                cursor.execute(
                    f"""
                    SELECT id::text AS value, name, phone, city, 'Dashboard' AS source
                    FROM relations
                    WHERE {where_relation}
                    ORDER BY
                        CASE WHEN %s = '' THEN updated_at ELSE NULL END DESC NULLS LAST,
                        name ASC
                    LIMIT %s;
                    """,
                    tuple([*params[:-1], search, params[-1]]),
                )
                return [
                    {
                        "value": row[0],
                        "name": row[1] or "",
                        "phone": row[2] or "",
                        "city": row[3] or "",
                        "source": row[4],
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def ensure_relation_for_candidate_match(match_value: str) -> int | None:
    value = str(match_value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return None


def list_principals(limit: int = 25, query: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                where_clause = ""
                if query:
                    where_clause = """
                    AND (
                       name ILIKE %s
                       OR email ILIKE %s
                       OR phone ILIKE %s
                       OR city ILIKE %s
                       OR status ILIKE %s
                    )
                    """
                    like_query = f"%{query}%"
                    params.extend([like_query] * 5)
                params.append(limit)
                cursor.execute(
                    f"""
                    SELECT id, name, email, phone, city, status, COALESCE(source, '')
                    FROM relations
                    WHERE relation_type = 'principal'
                      AND archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    {where_clause}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                return [
                    {
                        "id": row[0],
                        "type": "Opdrachtgever",
                        "name": row[1],
                        "contact": row[2] or row[3] or "-",
                        "city": row[4] or "-",
                        "status": row[5] or "Database",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_project_options(limit: int = 100) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT v.id,
                           v.title,
                           v.reference_number,
                           v.relation_name,
                           v.status,
                           v.payroll_cao_setting_id,
                           c.name
                    FROM vacancies v
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = v.payroll_cao_setting_id
                    WHERE COALESCE(v.raw_data->>'record_type', '') = 'project'
                       OR LOWER(COALESCE(v.status, '')) IN ('project', 'actief project', 'actief')
                    ORDER BY
                        CASE WHEN COALESCE(v.raw_data->>'record_type', '') = 'project' THEN 0 ELSE 1 END,
                        v.updated_at DESC,
                        v.id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "reference_number": row[2] or "",
                        "relation_name": row[3] or "",
                        "status": row[4] or "",
                        "payroll_cao_setting_id": row[5],
                        "cao_name": row[6] or "",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_relation_statuses(relation_type: str = "") -> list[str]:
    defaults = ["Actief", "Nieuw", "Nog beoordelen", "Via Website", "Werknemer ACTIEF", "In Reserve Houden", "Archief"]
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                filters = ["COALESCE(status, '') <> ''"]
                if relation_type in {"candidate", "principal"}:
                    filters.append("relation_type = %s")
                    params.append(relation_type)
                cursor.execute(
                    f"""
                    SELECT DISTINCT status
                    FROM relations
                    WHERE {' AND '.join(filters)}
                    ORDER BY status;
                    """,
                    tuple(params),
                )
                values = [row[0] for row in cursor.fetchall() if row[0]]
    except Exception:
        values = []

    return _unique_options([*defaults, *values])


def list_projects(limit: int = 100, query: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                filters = ["COALESCE(v.raw_data->>'record_type', '') = 'project'"]
                if query:
                    filters.append(
                        """
                        (
                            v.title ILIKE %s
                            OR v.reference_number ILIKE %s
                            OR v.relation_name ILIKE %s
                            OR v.location ILIKE %s
                            OR v.status ILIKE %s
                        )
                        """
                    )
                    like_query = f"%{query}%"
                    params.extend([like_query] * 5)
                params.append(limit)
                cursor.execute(
                    f"""
                    SELECT v.id,
                           v.title,
                           v.reference_number,
                           v.relation_name,
                           v.location,
                           v.status,
                           v.updated_at,
                           v.payroll_cao_setting_id,
                           c.name,
                           COUNT(b.id),
                           COALESCE(SUM(b.hours), 0),
                           MAX(b.work_date)
                    FROM vacancies v
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = v.payroll_cao_setting_id
                    LEFT JOIN project_time_bookings b
                        ON b.project_id = v.id
                    WHERE {' AND '.join(filters)}
                    GROUP BY v.id, c.name
                    ORDER BY v.updated_at DESC, v.id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                projects = [
                    {
                        "id": row[0],
                        "title": row[1],
                        "reference_number": row[2] or "",
                        "relation_name": row[3] or "",
                        "location": row[4] or "",
                        "status": row[5] or "Actief",
                        "updated_at": row[6].strftime("%d-%m-%Y %H:%M") if row[6] else "-",
                        "payroll_cao_setting_id": row[7],
                        "cao_name": row[8] or "Nog niet gekoppeld",
                        "booking_count": row[9] or 0,
                        "total_hours": _format_number(row[10]),
                        "last_booking_date": row[11].strftime("%d-%m-%Y") if row[11] else "-",
                        "recent_bookings": [],
                    }
                    for row in cursor.fetchall()
                ]
                _attach_project_bookings(cursor, projects)
                return projects
    except Exception:
        return []


def get_project(project_id: int | None) -> dict | None:
    if not project_id:
        return None
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT v.id,
                           v.title,
                           v.reference_number,
                           v.relation_name,
                           v.location,
                           v.status,
                           v.updated_at,
                           v.payroll_cao_setting_id,
                           c.name,
                           COUNT(b.id),
                           COALESCE(SUM(b.hours), 0),
                           MAX(b.work_date)
                    FROM vacancies v
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = v.payroll_cao_setting_id
                    LEFT JOIN project_time_bookings b
                        ON b.project_id = v.id
                    WHERE v.id = %s
                    GROUP BY v.id, c.name;
                    """,
                    (project_id,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        project = {
            "id": row[0],
            "title": row[1],
            "reference_number": row[2] or "",
            "relation_name": row[3] or "",
            "location": row[4] or "",
            "status": row[5] or "Actief",
            "updated_at": row[6].strftime("%d-%m-%Y %H:%M") if row[6] else "-",
            "payroll_cao_setting_id": row[7],
            "cao_name": row[8] or "Nog niet gekoppeld",
            "booking_count": row[9] or 0,
            "total_hours": _format_number(row[10]),
            "last_booking_date": row[11].strftime("%d-%m-%Y") if row[11] else "-",
            "recent_bookings": [],
            "bookings": list_project_time_bookings(project_id),
        }
        return project
    except Exception:
        return None


def list_project_time_bookings(project_id: int, limit: int = 250) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT b.id,
                           b.timesheet_inbox_id,
                           b.work_date,
                           b.hours,
                           b.status,
                           COALESCE(r.name, w.employee_name, w.matched_candidate_name, ''),
                           COALESCE(p.name, ''),
                           COALESCE(c.name, ''),
                           pp.name,
                           pp.year,
                           pp.period_number,
                           b.updated_at
                    FROM project_time_bookings b
                    LEFT JOIN relations r
                        ON r.id = b.relation_id
                    LEFT JOIN relations p
                        ON p.id = b.principal_id
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = b.payroll_cao_setting_id
                    LEFT JOIN payroll_periods pp
                        ON pp.id = b.payroll_period_id
                    LEFT JOIN whatsapp_timesheet_inbox w
                        ON w.id = b.timesheet_inbox_id
                    WHERE b.project_id = %s
                    ORDER BY b.work_date DESC NULLS LAST, b.updated_at DESC, b.id DESC
                    LIMIT %s;
                    """,
                    (project_id, limit),
                )
                return [
                    {
                        "id": row[0],
                        "timesheet_inbox_id": row[1],
                        "work_date": row[2].strftime("%d-%m-%Y") if row[2] else "-",
                        "hours": _format_number(row[3]),
                        "status": row[4] or "",
                        "employee_name": row[5] or "Onbekend",
                        "principal_name": row[6] or "-",
                        "cao_name": row[7] or "Nog niet gekoppeld",
                        "period_name": row[8] or "-",
                        "period_year": row[9],
                        "period_number": row[10],
                        "updated_at": row[11].strftime("%d-%m-%Y %H:%M") if row[11] else "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def create_project(data: dict) -> int:
    _ensure_dashboard_tables_for_read()
    raw_data = {
        "record_type": "project",
        "source": "dashboard",
        "notes": (data.get("notes") or "").strip(),
    }
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO vacancies (
                    title,
                    reference_number,
                    relation_name,
                    location,
                    status,
                    payroll_cao_setting_id,
                    publication_status,
                    website_enabled,
                    indeed_enabled,
                    raw_data,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'project', FALSE, FALSE, %s::jsonb, NOW(), NOW())
                RETURNING id;
                """,
                (
                    (data.get("title") or "").strip() or "Nieuw project",
                    (data.get("reference_number") or "").strip(),
                    (data.get("relation_name") or "").strip(),
                    (data.get("location") or "").strip(),
                    (data.get("status") or "").strip() or "Actief",
                    _int_or_none(data.get("payroll_cao_setting_id")),
                    json.dumps(raw_data),
                ),
            )
            project_id = cursor.fetchone()[0]
        conn.commit()
    return project_id


def _empty_to_none(value):
    text = str(value or "").strip()
    return text or None


def _number_or_none(value):
    text = str(value or "").strip().replace(",", ".")
    return text or None


def _decimal_or_none(value):
    text = str(value or "").strip().replace("€", "").replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _int_or_none(value):
    try:
        text = str(value or "").strip()
        return int(text) if text else None
    except Exception:
        return None


def _date_or_none(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except Exception:
        return None


def _format_number(value) -> str:
    if value is None:
        return "0"
    text = str(value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _format_money(value) -> str:
    if value is None:
        return "€ 0,00"
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {text}"


def list_payroll_periods(limit: int = 25, archived: bool = False) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        ensure_visible_demo_payroll_data()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.id,
                           p.year,
                           p.period_number,
                           p.name,
                           p.start_date,
                           p.end_date,
                           p.status,
                           p.notes,
                           COALESCE(w.week_count, 0),
                           COALESCE(b.booking_count, 0),
                           COALESCE(b.total_hours, 0),
                           p.updated_at
                    FROM payroll_periods p
                    LEFT JOIN (
                        SELECT payroll_period_id, COUNT(*) AS week_count
                        FROM payroll_period_weeks
                        GROUP BY payroll_period_id
                    ) w ON w.payroll_period_id = p.id
                    LEFT JOIN (
                        SELECT p2.id AS payroll_period_id,
                               COUNT(wi.id) AS booking_count,
                               SUM(
                                   COALESCE(
                                       wi.hours,
                                       b.hours,
                                       CASE
                                           WHEN COALESCE(wi.parsed_fields->'total_hours'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
                                           THEN REPLACE(wi.parsed_fields->'total_hours'->>'value', ',', '.')::numeric
                                           ELSE 0
                                       END
                                   )
                               ) AS total_hours
                        FROM payroll_periods p2
                        LEFT JOIN whatsapp_timesheet_inbox wi
                            ON LOWER(REPLACE(COALESCE(wi.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                           AND wi.deleted_at IS NULL
                           AND wi.archived_at IS NULL
                           AND COALESCE(wi.work_date, wi.received_at::date) BETWEEN p2.start_date AND p2.end_date
                        LEFT JOIN project_time_bookings b
                            ON b.timesheet_inbox_id = wi.id
                           AND LOWER(REPLACE(COALESCE(b.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                        WHERE wi.id IS NOT NULL
                        GROUP BY p2.id
                    ) b ON b.payroll_period_id = p.id
                    WHERE (
                        (%s = TRUE AND LOWER(COALESCE(p.status, '')) = 'archief')
                        OR (%s = FALSE AND LOWER(COALESCE(p.status, '')) <> 'archief')
                    )
                    ORDER BY p.start_date ASC NULLS LAST, p.end_date ASC NULLS LAST, p.year ASC, p.period_number ASC
                    LIMIT %s;
                    """,
                    (archived, archived, limit),
                )
                periods = [
                    {
                        "id": row[0],
                        "year": row[1],
                        "period_number": row[2],
                        "name": _payroll_period_name(row[2], row[4], row[5]) if row[4] and row[5] else row[3],
                        "start_date": row[4].strftime("%d-%m-%Y") if row[4] else "-",
                        "end_date": row[5].strftime("%d-%m-%Y") if row[5] else "-",
                        "status": row[6] or "concept",
                        "notes": row[7] or "",
                        "week_count": row[8] or 0,
                        "booking_count": row[9] or 0,
                        "total_hours": _format_number(row[10]),
                        "updated_at": row[11].strftime("%d-%m-%Y %H:%M") if row[11] else "-",
                        "weeks": [],
                    }
                    for row in cursor.fetchall()
                ]
                _apply_period_display_numbers(periods)
                _attach_period_weeks(cursor, periods)
                return periods
    except Exception:
        return []


def get_payroll_data_diagnostics() -> list[dict]:
    checks = [
        (
            "Kandidaten",
            """
            SELECT COUNT(*)
            FROM relations
            WHERE relation_type = 'candidate'
              AND archived_at IS NULL
              AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
            """,
            "relaties",
            1,
        ),
        (
            "Opdrachtgevers",
            """
            SELECT COUNT(*)
            FROM relations
            WHERE relation_type = 'principal'
              AND archived_at IS NULL
              AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
            """,
            "relaties",
            1,
        ),
        (
            "Loonperiodes 2026",
            "SELECT COUNT(*) FROM payroll_periods WHERE year = 2026 AND LOWER(COALESCE(status, '')) <> 'archief'",
            "periodes",
            PAYROLL_PERIODS_PER_YEAR,
        ),
        (
            "Periodeweken",
            """
            SELECT COUNT(*)
            FROM payroll_period_weeks w
            JOIN payroll_periods p ON p.id = w.payroll_period_id
            WHERE p.year = 2026
            """,
            "weken",
            PAYROLL_PERIODS_PER_YEAR * 4,
        ),
        ("Urenbriefjes", "SELECT COUNT(*) FROM whatsapp_timesheet_inbox WHERE deleted_at IS NULL AND archived_at IS NULL", "taken", 1),
        ("Projectboekingen", "SELECT COUNT(*) FROM project_time_bookings", "boekingen", 1),
        ("Weekinvoer", "SELECT COUNT(*) FROM payroll_week_inputs", "regels", 1),
        ("Weekresultaten", "SELECT COUNT(*) FROM payroll_week_results", "resultaten", 1),
        ("Audit", "SELECT COUNT(*) FROM audit_events", "events", 1),
        ("AI/OCR audit", "SELECT COUNT(*) FROM openai_api_audit_events", "events", 1),
    ]
    diagnostics = []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                for label, query, suffix, target in checks:
                    try:
                        cursor.execute(query)
                        value = int(cursor.fetchone()[0] or 0)
                        tone = "green" if value >= target else "orange" if value else "red"
                        diagnostics.append(
                            {
                                "label": label,
                                "value": value,
                                "suffix": suffix,
                                "target": target,
                                "tone": tone,
                                "status": "gevuld" if value else "leeg",
                            }
                        )
                    except Exception as exc:
                        conn.rollback()
                        diagnostics.append(
                            {
                                "label": label,
                                "value": "-",
                                "suffix": suffix,
                                "target": target,
                                "tone": "red",
                                "status": type(exc).__name__,
                            }
                        )
    except Exception as exc:
        print(f"PAYROLL_DATA_DIAGNOSTICS_ERROR {type(exc).__name__}: {exc}")
    return diagnostics


def list_payroll_year_overview(limit: int = 5) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payroll_year_id,
                           year,
                           expected_period_count,
                           expected_weeks_per_period,
                           actual_period_count,
                           actual_week_count,
                           first_period_start_date,
                           last_period_end_date,
                           status,
                           updated_at
                    FROM payroll_year_overview
                    ORDER BY year DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        return [_payroll_year_overview_row(row) for row in rows]
    except Exception:
        return []


def _payroll_year_overview_row(row) -> dict:
    return {
        "payroll_year_id": row[0],
        "year": row[1],
        "expected_period_count": row[2] or PAYROLL_PERIODS_PER_YEAR,
        "expected_weeks_per_period": row[3] or 4,
        "actual_period_count": row[4] or 0,
        "actual_week_count": row[5] or 0,
        "first_period_start_date": row[6].strftime("%d-%m-%Y") if row[6] else "-",
        "last_period_end_date": row[7].strftime("%d-%m-%Y") if row[7] else "-",
        "status": row[8] or "concept",
        "updated_at": row[9].strftime("%d-%m-%Y %H:%M") if row[9] else "-",
    }


def list_payroll_datamodel_status(year: int | None = None, limit: int = 25) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                if year:
                    cursor.execute(
                        """
                        SELECT payroll_period_id,
                               year,
                               period_number,
                               period_name,
                               start_date,
                               end_date,
                               period_status,
                               week_count,
                               week_input_count,
                               week_line_count,
                               week_result_count,
                               period_settlement_count,
                               employee_arrangement_count,
                               parameter_version_count,
                               running_balance_account_count,
                               running_balance_mutation_count,
                               audit_event_count,
                               openai_api_audit_event_count,
                               week_structure_status,
                               updated_at
                        FROM payroll_period_datamodel_status
                        WHERE year = %s
                        ORDER BY period_number ASC
                        LIMIT %s;
                        """,
                        (year, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT payroll_period_id,
                               year,
                               period_number,
                               period_name,
                               start_date,
                               end_date,
                               period_status,
                               week_count,
                               week_input_count,
                               week_line_count,
                               week_result_count,
                               period_settlement_count,
                               employee_arrangement_count,
                               parameter_version_count,
                               running_balance_account_count,
                               running_balance_mutation_count,
                               audit_event_count,
                               openai_api_audit_event_count,
                               week_structure_status,
                               updated_at
                        FROM payroll_period_datamodel_status
                        ORDER BY year DESC, period_number ASC
                        LIMIT %s;
                        """,
                        (limit,),
                    )
                rows = cursor.fetchall()
        return [_payroll_datamodel_status_row(row) for row in rows]
    except Exception:
        return []


def _payroll_datamodel_status_row(row) -> dict:
    return {
        "payroll_period_id": row[0],
        "year": row[1],
        "period_number": row[2],
        "period_name": row[3] or f"Periode {row[2]}",
        "start_date": row[4].strftime("%d-%m-%Y") if row[4] else "-",
        "end_date": row[5].strftime("%d-%m-%Y") if row[5] else "-",
        "period_status": row[6] or "concept",
        "week_count": row[7] or 0,
        "week_input_count": row[8] or 0,
        "week_line_count": row[9] or 0,
        "week_result_count": row[10] or 0,
        "period_settlement_count": row[11] or 0,
        "employee_arrangement_count": row[12] or 0,
        "parameter_version_count": row[13] or 0,
        "running_balance_account_count": row[14] or 0,
        "running_balance_mutation_count": row[15] or 0,
        "audit_event_count": row[16] or 0,
        "openai_api_audit_event_count": row[17] or 0,
        "week_structure_status": row[18] or "onbekend",
        "updated_at": row[19].strftime("%d-%m-%Y %H:%M") if row[19] else "-",
    }

def get_payroll_period_datamodel_status(period_id: int | None) -> dict | None:
    if not period_id:
        return None
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payroll_period_id,
                           year,
                           period_number,
                           period_name,
                           start_date,
                           end_date,
                           period_status,
                           week_count,
                           week_input_count,
                           week_line_count,
                           week_result_count,
                           period_settlement_count,
                           employee_arrangement_count,
                           parameter_version_count,
                           running_balance_account_count,
                           running_balance_mutation_count,
                           audit_event_count,
                           openai_api_audit_event_count,
                           week_structure_status,
                           updated_at
                    FROM payroll_period_datamodel_status
                    WHERE payroll_period_id = %s
                    LIMIT 1;
                    """,
                    (period_id,),
                )
                row = cursor.fetchone()
        return _payroll_datamodel_status_row(row) if row else None
    except Exception:
        return None


def get_payroll_period_defaults() -> dict:
    today = date.today()
    fallback_start = today - timedelta(days=today.weekday())
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT year, period_number, end_date
                    FROM payroll_periods
                    WHERE LOWER(COALESCE(status, '')) <> 'archief'
                    ORDER BY end_date DESC NULLS LAST, year DESC, period_number DESC
                    LIMIT 1;
                    """
                )
                row = cursor.fetchone()
                if row and row[2]:
                    next_start = row[2] + timedelta(days=1)
                    next_year = next_start.year
                else:
                    next_start = fallback_start
                    next_year = next_start.year
                next_end = next_start + timedelta(days=27)
                cursor.execute(
                    """
                    SELECT period_number
                    FROM payroll_periods
                    WHERE year = %s
                      AND LOWER(COALESCE(status, '')) <> 'archief'
                    ORDER BY period_number;
                    """,
                    (next_year,),
                )
                used_numbers = {
                    int(number or 0)
                    for (number,) in cursor.fetchall()
                    if 1 <= int(number or 0) <= PAYROLL_PERIODS_PER_YEAR
                }
                available_numbers = [
                    number
                    for number in range(1, PAYROLL_PERIODS_PER_YEAR + 1)
                    if number not in used_numbers
                ]
                next_number = available_numbers[0] if available_numbers else PAYROLL_PERIODS_PER_YEAR
                remaining_period_count = len(available_numbers)
                return {
                    "year": next_year,
                    "period_number": next_number,
                    "display_period_number": next_number,
                    "remaining_period_count": remaining_period_count,
                    "max_period_count": PAYROLL_PERIODS_PER_YEAR,
                    "can_create": remaining_period_count > 0,
                    "start_date": next_start.isoformat(),
                    "end_date": next_end.isoformat(),
                    "name": _payroll_period_name(next_number, next_start, next_end) if remaining_period_count else f"Loonjaar {next_year} compleet",
                }
    except Exception:
        fallback_end = fallback_start + timedelta(days=27)
        return {
            "year": fallback_start.year,
            "period_number": 1,
            "display_period_number": 1,
            "remaining_period_count": PAYROLL_PERIODS_PER_YEAR,
            "max_period_count": PAYROLL_PERIODS_PER_YEAR,
            "can_create": True,
            "start_date": fallback_start.isoformat(),
            "end_date": fallback_end.isoformat(),
            "name": _payroll_period_name(1, fallback_start, fallback_end),
        }


def get_payroll_period(period_id: int | None) -> dict | None:
    if not period_id:
        return None
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.id,
                           p.year,
                           p.period_number,
                           p.name,
                           p.start_date,
                           p.end_date,
                           p.status,
                           p.notes,
                           COALESCE(w.week_count, 0),
                           COALESCE(b.booking_count, 0),
                           COALESCE(b.total_hours, 0),
                           p.updated_at
                    FROM payroll_periods p
                    LEFT JOIN (
                        SELECT payroll_period_id, COUNT(*) AS week_count
                        FROM payroll_period_weeks
                        GROUP BY payroll_period_id
                    ) w ON w.payroll_period_id = p.id
                    LEFT JOIN (
                        SELECT p2.id AS payroll_period_id,
                               COUNT(wi.id) AS booking_count,
                               SUM(
                                   COALESCE(
                                       wi.hours,
                                       b.hours,
                                       CASE
                                           WHEN COALESCE(wi.parsed_fields->'total_hours'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
                                           THEN REPLACE(wi.parsed_fields->'total_hours'->>'value', ',', '.')::numeric
                                           ELSE 0
                                       END
                                   )
                               ) AS total_hours
                        FROM payroll_periods p2
                        LEFT JOIN whatsapp_timesheet_inbox wi
                            ON LOWER(REPLACE(COALESCE(wi.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                           AND wi.deleted_at IS NULL
                           AND wi.archived_at IS NULL
                           AND COALESCE(wi.work_date, wi.received_at::date) BETWEEN p2.start_date AND p2.end_date
                        LEFT JOIN project_time_bookings b
                            ON b.timesheet_inbox_id = wi.id
                           AND LOWER(REPLACE(COALESCE(b.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                        WHERE p2.id = %s
                          AND wi.id IS NOT NULL
                        GROUP BY p2.id
                    ) b ON b.payroll_period_id = p.id
                    WHERE p.id = %s;
                    """,
                    (period_id, period_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                period = {
                    "id": row[0],
                    "year": row[1],
                    "period_number": row[2],
                    "display_period_number": row[2],
                    "name": _payroll_period_name(row[2], row[4], row[5]) if row[4] and row[5] else row[3],
                    "start_date": row[4].strftime("%d-%m-%Y") if row[4] else "-",
                    "end_date": row[5].strftime("%d-%m-%Y") if row[5] else "-",
                    "status": row[6] or "concept",
                    "notes": row[7] or "",
                    "week_count": row[8] or 0,
                    "booking_count": row[9] or 0,
                    "total_hours": _format_number(row[10]),
                    "updated_at": row[11].strftime("%d-%m-%Y %H:%M") if row[11] else "-",
                    "weeks": [],
                }
                _attach_period_weeks(cursor, [period])
        period["datamodel_status"] = get_payroll_period_datamodel_status(period_id)
        period["week_input_summary"] = get_payroll_week_input_summary(period_id)
        period["week_result_summary"] = get_payroll_week_result_summary(period_id)
        period["payroll_exceptions"] = list_payroll_period_exceptions(period_id)
        period["payroll_exception_summary"] = summarize_payroll_exceptions(period["payroll_exceptions"])
        period["payroll_phase_status"] = payroll_phase_status(period["week_result_summary"], period["payroll_exception_summary"])
        period["period_settlements"] = list_payroll_period_settlements(period_id)
        period["employee_week_results"] = period["period_settlements"] or list_payroll_employee_week_results(period_id)
        period["payroll_rows"] = list_payroll_period_payroll(period_id)
        period["payroll_totals"] = _payroll_period_totals(period["payroll_rows"])
        stored_totals = list_payroll_period_totals(period_id)
        period["period_calculation_rows"] = stored_totals or derived_period_total_rows(period["payroll_rows"])
        sheet_candidates = list_payroll_sheet_candidates()
        period["period_sheet_rows"] = build_period_sheet_rows(sheet_candidates, period["payroll_rows"])
        period["payslip_sheet_rows"] = build_payslip_sheet_rows(period["period_sheet_rows"], period["period_calculation_rows"])
        period["workbook_tabs"] = build_workbook_tabs(
            period["weeks"],
            sheet_candidates,
            period["payroll_rows"],
            period["period_calculation_rows"],
        )
        apply_payroll_workbook_overrides(period_id, period["workbook_tabs"])
        for tab in period["workbook_tabs"]:
            if tab.get("kind") == "week":
                tab["summary"] = summarize_week_rows(tab.get("rows", []))
        period["payroll_totals"] = summarize_workbook_tabs(period["workbook_tabs"])
        period["payroll_import_logs"] = list_payroll_import_logs(period_id)
        period["payroll_calculation_rules"] = list_payroll_calculation_rules()
        period["payroll_validation_results"] = list_payroll_validation_results(period_id)
        return period
    except Exception:
        return None


def list_payroll_period_settlements(period_id: int, limit: int = 200) -> list[dict]:
    if not period_id:
        return []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT relation_id,
                           employee_name,
                           week_count,
                           total_worked_hours,
                           total_km,
                           net_wage_amount,
                           travel_amount,
                           day_allowance_amount,
                           advance_weeks_1_3,
                           week_4_amount,
                           total_period_amount,
                           payment_schedule,
                           settlement_status,
                           status_details
                    FROM payroll_period_settlements
                    WHERE payroll_period_id = %s
                    ORDER BY employee_name ASC
                    LIMIT %s;
                    """,
                    (period_id, limit),
                )
                return [_payroll_period_settlement_row((*row, None, None, None)) for row in cursor.fetchall()]
    except Exception:
        return []


def list_payroll_employee_week_results(period_id: int, limit: int = 200) -> list[dict]:
    if not period_id:
        return []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COALESCE(r.relation_id, 0) AS relation_key,
                           MAX(r.relation_id) AS relation_id,
                           r.employee_name,
                           COUNT(*) AS week_count,
                           COALESCE(SUM(r.worked_hours), 0) AS worked_hours,
                           COALESCE(SUM(r.total_km), 0) AS total_km,
                           COALESCE(SUM(r.net_wage_amount), 0) AS net_wage_amount,
                           COALESCE(SUM(r.travel_amount), 0) AS travel_amount,
                           COALESCE(SUM(r.day_allowance_amount), 0) AS day_allowance_amount,
                           COALESCE(SUM(r.net_week_total), 0) AS net_period_total,
                           COALESCE(SUM(r.net_week_total) FILTER (WHERE w.week_index BETWEEN 1 AND 3), 0) AS advance_weeks_1_3,
                           COALESCE(SUM(r.net_week_total) FILTER (WHERE w.week_index = 4), 0) AS week_4_amount,
                           COUNT(*) FILTER (WHERE r.calculation_status = 'concept') AS concept_count,
                           COUNT(*) FILTER (WHERE r.calculation_status = 'mist_inrichting') AS missing_arrangement_count,
                           COUNT(*) FILTER (WHERE r.calculation_status = 'mist_netto_basisloon') AS missing_wage_count,
                           STRING_AGG(DISTINCT r.calculation_status, ', ' ORDER BY r.calculation_status) AS statuses
                    FROM payroll_week_results r
                    LEFT JOIN payroll_period_weeks w ON w.id = r.payroll_period_week_id
                    WHERE r.payroll_period_id = %s
                    GROUP BY COALESCE(r.relation_id, 0), r.employee_name
                    ORDER BY r.employee_name ASC
                    LIMIT %s;
                    """,
                    (period_id, limit),
                )
                return [
                    {
                        "relation_id": row[1],
                        "employee_name": row[2] or "Onbekend",
                        "week_count": row[3] or 0,
                        "worked_hours": _format_number(row[4]),
                        "total_km": _format_number(row[5]),
                        "net_wage_amount": _format_money(row[6]),
                        "travel_amount": _format_money(row[7]),
                        "day_allowance_amount": _format_money(row[8]),
                        "net_period_total": _format_money(row[9]),
                        "advance_weeks_1_3": _format_money(row[10]),
                        "week_4_amount": _format_money(row[11]),
                        "concept_count": row[12] or 0,
                        "missing_arrangement_count": row[13] or 0,
                        "missing_wage_count": row[14] or 0,
                        "statuses": row[15] or "concept",
                        "status_label": _employee_week_result_status(row[12], row[13], row[14]),
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def _employee_week_result_status(concept_count, missing_arrangement_count, missing_wage_count) -> str:
    if missing_arrangement_count:
        return "mist inrichting"
    if missing_wage_count:
        return "mist netto basisloon"
    if concept_count:
        return "concept"
    return "controle"


def get_payroll_week_result_summary(period_id: int) -> dict:
    zero_money = _format_money(0)
    empty = {
        "result_count": 0,
        "total_net_week": zero_money,
        "net_wage_amount": zero_money,
        "travel_amount": zero_money,
        "day_allowance_amount": zero_money,
        "concept_count": 0,
        "missing_arrangement_count": 0,
        "missing_wage_count": 0,
        "status_counts": [],
    }
    if not period_id:
        return empty
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COALESCE(SUM(net_week_total), 0),
                           COALESCE(SUM(net_wage_amount), 0),
                           COALESCE(SUM(travel_amount), 0),
                           COALESCE(SUM(day_allowance_amount), 0),
                           COUNT(*) FILTER (WHERE calculation_status = 'concept'),
                           COUNT(*) FILTER (WHERE calculation_status = 'mist_inrichting'),
                           COUNT(*) FILTER (WHERE calculation_status = 'mist_netto_basisloon')
                    FROM payroll_week_results
                    WHERE payroll_period_id = %s;
                    """,
                    (period_id,),
                )
                row = cursor.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0)
                cursor.execute(
                    """
                    SELECT COALESCE(calculation_status, 'concept'), COUNT(*)
                    FROM payroll_week_results
                    WHERE payroll_period_id = %s
                    GROUP BY COALESCE(calculation_status, 'concept')
                    ORDER BY COUNT(*) DESC, COALESCE(calculation_status, 'concept');
                    """,
                    (period_id,),
                )
                status_counts = [
                    {"status": status, "count": count}
                    for status, count in cursor.fetchall()
                ]
        return {
            "result_count": row[0] or 0,
            "total_net_week": _format_money(row[1]),
            "net_wage_amount": _format_money(row[2]),
            "travel_amount": _format_money(row[3]),
            "day_allowance_amount": _format_money(row[4]),
            "concept_count": row[5] or 0,
            "missing_arrangement_count": row[6] or 0,
            "missing_wage_count": row[7] or 0,
            "status_counts": status_counts,
        }
    except Exception:
        return empty


def payroll_phase_status(week_result_summary: dict | None, exception_summary: dict | None) -> dict:
    week_result_summary = week_result_summary or {}
    exception_summary = exception_summary or {}
    result_count = int(week_result_summary.get("result_count") or 0)
    blocking = int(exception_summary.get("blocking") or 0)
    warning = int(exception_summary.get("warning") or 0)
    total = int(exception_summary.get("total") or 0)

    if result_count == 0:
        return {
            "label": "Nog niet berekend",
            "tone": "warning",
            "can_approve": False,
            "detail": "Er zijn nog geen gevalideerde uren of weekresultaten voor deze periode.",
            "audit_summary": "geen gevalideerde uren",
        }
    if blocking > 0:
        return {
            "label": "Controle vereist",
            "tone": "danger",
            "can_approve": False,
            "detail": f"Los eerst {blocking} blokkerende payroll-uitzondering(en) op.",
            "audit_summary": f"{blocking} blokkerend, {warning} nalopen",
        }
    if warning > 0:
        return {
            "label": "Nalopen voor akkoord",
            "tone": "warning",
            "can_approve": True,
            "detail": f"Er zijn {warning} aandachtspunt(en); accorderen kan na inhoudelijke controle.",
            "audit_summary": f"0 blokkerend, {warning} nalopen",
        }
    return {
        "label": "Controlelaag compleet",
        "tone": "success",
        "can_approve": True,
        "detail": "Er zijn geen bekende payroll-uitzonderingen gevonden.",
        "audit_summary": f"{total} uitzonderingen",
    }


def list_payroll_period_exceptions(period_id: int, limit: int = 100) -> list[dict]:
    if not period_id:
        return []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    WITH input_project_counts AS (
                        SELECT payroll_week_input_id, COUNT(*) AS project_count
                        FROM payroll_week_input_projects
                        GROUP BY payroll_week_input_id
                    ), exceptions AS (
                        SELECT 'missing_relation' AS exception_key,
                               'blokkerend' AS severity,
                               NULL::integer AS relation_id,
                               i.employee_name,
                               COUNT(*) AS occurrence_count,
                               STRING_AGG(DISTINCT COALESCE(i.week_number::text, '-'), ', ' ORDER BY COALESCE(i.week_number::text, '-')) AS week_numbers,
                               'Kandidaatkoppeling ontbreekt' AS title,
                               'Koppel deze week-invoer aan de juiste medewerkerkaart voordat de periode betrouwbaar is.' AS detail,
                               'Urenbriefje controleren' AS next_step
                        FROM payroll_week_inputs i
                        WHERE i.payroll_period_id = %s
                          AND i.relation_id IS NULL
                        GROUP BY i.employee_name

                        UNION ALL

                        SELECT 'missing_arrangement' AS exception_key,
                               'blokkerend' AS severity,
                               i.relation_id,
                               i.employee_name,
                               COUNT(*) AS occurrence_count,
                               STRING_AGG(DISTINCT COALESCE(i.week_number::text, '-'), ', ' ORDER BY COALESCE(i.week_number::text, '-')) AS week_numbers,
                               'Medewerkerinrichting ontbreekt' AS title,
                               'Leg de verloningsinrichting vast op de medewerkerkaart voor deze periode.' AS detail,
                               'Medewerkerkaart openen' AS next_step
                        FROM payroll_week_inputs i
                        WHERE i.payroll_period_id = %s
                          AND i.relation_id IS NOT NULL
                          AND i.arrangement_id IS NULL
                        GROUP BY i.relation_id, i.employee_name

                        UNION ALL

                        SELECT 'missing_net_base' AS exception_key,
                               'blokkerend' AS severity,
                               r.relation_id,
                               r.employee_name,
                               COUNT(*) AS occurrence_count,
                               STRING_AGG(DISTINCT COALESCE(r.week_number::text, '-'), ', ' ORDER BY COALESCE(r.week_number::text, '-')) AS week_numbers,
                               'Netto basisloon ontbreekt' AS title,
                               'Vul netto basis 40 uur in zodat de netto indicatie per week en periode kan worden berekend.' AS detail,
                               'Medewerkerkaart openen' AS next_step
                        FROM payroll_week_results r
                        WHERE r.payroll_period_id = %s
                          AND r.calculation_status = 'mist_netto_basisloon'
                        GROUP BY r.relation_id, r.employee_name

                        UNION ALL

                        SELECT 'incomplete_period' AS exception_key,
                               'waarschuwing' AS severity,
                               s.relation_id,
                               s.employee_name,
                               GREATEST(4 - COALESCE(s.week_count, 0), 0) AS occurrence_count,
                               '-' AS week_numbers,
                               'Periode niet compleet' AS title,
                               'Deze medewerker heeft minder dan vier weekregels in deze periode.' AS detail,
                               'Week-invoer controleren' AS next_step
                        FROM payroll_period_settlements s
                        WHERE s.payroll_period_id = %s
                          AND COALESCE(s.week_count, 0) < 4

                        UNION ALL

                        SELECT 'missing_project_booking' AS exception_key,
                               'waarschuwing' AS severity,
                               i.relation_id,
                               i.employee_name,
                               COUNT(*) AS occurrence_count,
                               STRING_AGG(DISTINCT COALESCE(i.week_number::text, '-'), ', ' ORDER BY COALESCE(i.week_number::text, '-')) AS week_numbers,
                               'Projectregel ontbreekt' AS title,
                               'Er zijn uren verwerkt zonder gekoppelde projectregel; controleer opdrachtgever/project voor facturatie en CAO-context.' AS detail,
                               'Urenbriefje controleren' AS next_step
                        FROM payroll_week_inputs i
                        LEFT JOIN input_project_counts pc ON pc.payroll_week_input_id = i.id
                        WHERE i.payroll_period_id = %s
                          AND COALESCE(i.worked_hours, 0) > 0
                          AND COALESCE(pc.project_count, 0) = 0
                        GROUP BY i.relation_id, i.employee_name
                    )
                    SELECT exception_key, severity, relation_id, employee_name, occurrence_count,
                           week_numbers, title, detail, next_step
                    FROM exceptions
                    WHERE occurrence_count > 0
                    ORDER BY CASE severity WHEN 'blokkerend' THEN 1 WHEN 'waarschuwing' THEN 2 ELSE 3 END,
                             employee_name ASC, title ASC
                    LIMIT %s;
                    """,
                    (period_id, period_id, period_id, period_id, period_id, limit),
                )
                rows = cursor.fetchall()
        return [
            {
                "exception_key": row[0],
                "severity": row[1],
                "severity_label": _payroll_exception_severity_label(row[1]),
                "relation_id": row[2],
                "employee_name": row[3] or "Onbekend",
                "occurrence_count": row[4] or 0,
                "week_numbers": row[5] or "-",
                "title": row[6],
                "detail": row[7],
                "next_step": row[8],
            }
            for row in rows
        ]
    except Exception:
        return []


def _payroll_exception_severity_label(severity: str) -> str:
    if severity == "blokkerend":
        return "Blokkeert"
    if severity == "waarschuwing":
        return "Nalopen"
    return "Info"


def summarize_payroll_exceptions(exceptions: list[dict]) -> dict:
    summary = {"total": len(exceptions), "blocking": 0, "warning": 0, "info": 0}
    for item in exceptions:
        severity = item.get("severity")
        if severity == "blokkerend":
            summary["blocking"] += 1
        elif severity == "waarschuwing":
            summary["warning"] += 1
        else:
            summary["info"] += 1
    return summary


def get_payroll_week_input_summary(period_id: int) -> dict:
    empty = {
        "input_count": 0,
        "day_count": 0,
        "project_count": 0,
        "total_hours": "0",
        "total_km": "0",
        "with_arrangement": 0,
        "without_arrangement": 0,
        "status_counts": [],
    }
    if not period_id:
        return empty
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*),
                           COALESCE(SUM(worked_hours), 0),
                           COALESCE(SUM(total_km), 0),
                           COUNT(*) FILTER (WHERE arrangement_id IS NOT NULL),
                           COUNT(*) FILTER (WHERE arrangement_id IS NULL)
                    FROM payroll_week_inputs
                    WHERE payroll_period_id = %s;
                    """,
                    (period_id,),
                )
                summary_row = cursor.fetchone() or (0, 0, 0, 0, 0)
                cursor.execute(
                    """
                    SELECT COUNT(d.id)
                    FROM payroll_week_input_days d
                    JOIN payroll_week_inputs i ON i.id = d.payroll_week_input_id
                    WHERE i.payroll_period_id = %s;
                    """,
                    (period_id,),
                )
                day_count = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COUNT(p.id)
                    FROM payroll_week_input_projects p
                    JOIN payroll_week_inputs i ON i.id = p.payroll_week_input_id
                    WHERE i.payroll_period_id = %s;
                    """,
                    (period_id,),
                )
                project_count = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT COALESCE(status, 'concept'), COUNT(*)
                    FROM payroll_week_inputs
                    WHERE payroll_period_id = %s
                    GROUP BY COALESCE(status, 'concept')
                    ORDER BY COUNT(*) DESC, COALESCE(status, 'concept');
                    """,
                    (period_id,),
                )
                status_counts = [
                    {"status": row[0], "count": row[1]}
                    for row in cursor.fetchall()
                ]
        return {
            "input_count": summary_row[0] or 0,
            "day_count": day_count or 0,
            "project_count": project_count or 0,
            "total_hours": _format_number(summary_row[1]),
            "total_km": _format_number(summary_row[2]),
            "with_arrangement": summary_row[3] or 0,
            "without_arrangement": summary_row[4] or 0,
            "status_counts": status_counts,
        }
    except Exception:
        return empty


def list_payroll_period_payroll(period_id: int) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, start_date, end_date
                    FROM payroll_periods
                    WHERE id = %s;
                    """,
                    (period_id,),
                )
                period_row = cursor.fetchone()
                if not period_row:
                    return []
                _, start_date, end_date = period_row
                cursor.execute(
                    """
                    SELECT week_index, start_date, end_date
                    FROM payroll_period_weeks
                    WHERE payroll_period_id = %s
                    ORDER BY week_index;
                    """,
                    (period_id,),
                )
                weeks = cursor.fetchall()
                cursor.execute(
                    """
                    WITH booking_context AS (
                        SELECT timesheet_inbox_id,
                               MAX(relation_id) AS relation_id,
                               MAX(principal_id) AS principal_id,
                               MAX(project_id) AS project_id,
                               MAX(payroll_cao_setting_id) AS payroll_cao_setting_id,
                               SUM(hours) AS booking_hours,
                               STRING_AGG(DISTINCT status, ', ') AS booking_status
                        FROM project_time_bookings
                        WHERE LOWER(REPLACE(COALESCE(status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                        GROUP BY timesheet_inbox_id
                    )
                    SELECT w.id,
                           COALESCE(w.matched_relation_id, b.relation_id) AS relation_id,
                           COALESCE(r.name, w.employee_name, w.matched_candidate_name, 'Onbekend') AS employee_name,
                           COALESCE(c.name, 'Geen CAO') AS cao_name,
                           COALESCE(c.standard_week_hours, 40) AS standard_week_hours,
                           COALESCE(c.weekday_overtime_percent, 125) AS weekday_overtime_percent,
                           r.hourly_rate,
                           COALESCE(c.default_hourly_wage, 0) AS cao_hourly_wage,
                           COALESCE(v.title, w.project_name, '-') AS project_name,
                           COALESCE(p.name, w.principal_name, '-') AS principal_name,
                           COALESCE(w.work_date, w.received_at::date) AS work_date,
                           COALESCE(
                               w.hours,
                               b.booking_hours,
                               CASE
                                   WHEN COALESCE(w.parsed_fields->'total_hours'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
                                   THEN REPLACE(w.parsed_fields->'total_hours'->>'value', ',', '.')::numeric
                                   ELSE 0
                               END
                           ) AS hours,
                           COALESCE(b.booking_status, w.status) AS status,
                           r.payroll_license_plate,
                           r.payroll_choice_budget,
                           r.payroll_phase,
                           r.payroll_pension,
                           r.payroll_cao_hours,
                           r.payroll_days_right,
                           r.payroll_scale,
                           r.payroll_function,
                           r.payroll_hourly_wage
                    FROM whatsapp_timesheet_inbox w
                    LEFT JOIN booking_context b
                        ON b.timesheet_inbox_id = w.id
                    LEFT JOIN relations r
                        ON r.id = COALESCE(w.matched_relation_id, b.relation_id)
                    LEFT JOIN relations p
                        ON p.id = COALESCE(w.selected_principal_id, b.principal_id)
                    LEFT JOIN vacancies v
                        ON v.id = COALESCE(w.selected_project_id, b.project_id)
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = COALESCE(b.payroll_cao_setting_id, v.payroll_cao_setting_id)
                    WHERE LOWER(REPLACE(COALESCE(w.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
                      AND w.deleted_at IS NULL
                      AND w.archived_at IS NULL
                      AND COALESCE(w.work_date, w.received_at::date) BETWEEN %s AND %s
                    ORDER BY employee_name, work_date, w.id;
                    """,
                    (start_date, end_date),
                )
                aggregates: dict[tuple, dict] = {}
                for row in cursor.fetchall():
                    key = (row[1], row[2], row[3])
                    item = aggregates.setdefault(
                        key,
                        {
                            "employee_name": row[2],
                            "cao_name": row[3],
                            "standard_week_hours_raw": Decimal(str(row[4] or 40)),
                            "overtime_percent_raw": Decimal(str(row[5] or 125)),
                            "candidate_hourly_wage_raw": _decimal_or_none(row[6]),
                            "cao_hourly_wage_raw": Decimal(str(row[7] or 0)),
                            "projects": set(),
                            "principals": set(),
                            "statuses": set(),
                            "dates": set(),
                            "booking_count": 0,
                            "total_hours_raw": Decimal("0"),
                            "week_hours_raw": [Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")],
                            "relation_id": row[1],
                            "payroll_license_plate": row[13] or "",
                            "payroll_choice_budget": row[14] or "",
                            "payroll_phase": row[15] or "",
                            "payroll_pension": row[16] or "",
                            "payroll_cao_hours": row[17] or "",
                            "payroll_days_right": row[18] or "",
                            "payroll_scale": row[19] or "",
                            "payroll_function": row[20] or "",
                            "payroll_hourly_wage": row[21] or "",
                        },
                    )
                    hours = Decimal(str(row[11] or 0))
                    item["booking_count"] += 1
                    item["total_hours_raw"] += hours
                    item["projects"].add(row[8] or "-")
                    item["principals"].add(row[9] or "-")
                    item["statuses"].add(row[12] or "concept")
                    if row[10]:
                        item["dates"].add(row[10])
                        for week_index, week_start, week_end in weeks:
                            if week_start <= row[10] <= week_end and 1 <= week_index <= 4:
                                item["week_hours_raw"][week_index - 1] += hours
                                break
                rows = []
                for item in aggregates.values():
                    standard = item["standard_week_hours_raw"]
                    overtime_percent = item["overtime_percent_raw"] / Decimal("100")
                    candidate_wage = item["candidate_hourly_wage_raw"]
                    wage = candidate_wage if candidate_wage is not None else item["cao_hourly_wage_raw"]
                    normal_hours = sum(min(week_hours, standard) for week_hours in item["week_hours_raw"])
                    overtime_hours = sum(max(Decimal("0"), week_hours - standard) for week_hours in item["week_hours_raw"])
                    gross_amount = (normal_hours * wage) + (overtime_hours * wage * overtime_percent)
                    rows.append(
                        {
                            "employee_name": item["employee_name"],
                            "relation_id": item["relation_id"],
                            "cao_name": item["cao_name"],
                            "projects": ", ".join(sorted(item["projects"])),
                            "principals": ", ".join(sorted(item["principals"])),
                            "booking_count": item["booking_count"],
                            "worked_days": len(item["dates"]),
                            "total_hours": _format_number(item["total_hours_raw"]),
                            "week_hours": [_format_number(value) for value in item["week_hours_raw"]],
                            "normal_hours": _format_number(normal_hours),
                            "overtime_hours": _format_number(overtime_hours),
                            "hourly_wage": _format_money(wage),
                            "hourly_wage_source": "Kandidaat" if candidate_wage is not None else "CAO default",
                            "gross_amount": _format_money(gross_amount),
                            "status": ", ".join(sorted(item["statuses"])),
                            "payroll_license_plate": item["payroll_license_plate"],
                            "payroll_choice_budget": item["payroll_choice_budget"],
                            "payroll_phase": item["payroll_phase"],
                            "payroll_pension": item["payroll_pension"],
                            "payroll_cao_hours": item["payroll_cao_hours"],
                            "payroll_days_right": item["payroll_days_right"],
                            "payroll_scale": item["payroll_scale"],
                            "payroll_function": item["payroll_function"],
                            "payroll_hourly_wage": item["payroll_hourly_wage"],
                        }
                    )
                return sorted(rows, key=lambda item: item["employee_name"])
    except Exception:
        return []


def create_manual_timesheet(data: dict) -> int:
    _ensure_dashboard_tables_for_read()
    work_date = _date_or_none(data.get("work_date")) or date.today()
    hours = _decimal_or_none(data.get("hours")) or Decimal("0")
    relation_id = _int_or_none(data.get("relation_id"))
    principal_id = _int_or_none(data.get("principal_id"))
    project_id = _int_or_none(data.get("project_id"))
    status = (data.get("status") or "controle").strip() or "controle"
    if status not in {"controle", "goed_te_keuren", "loon_te_berekenen"}:
        status = "controle"
    with get_connection() as conn:
        with conn.cursor() as cursor:
            candidate_name = (data.get("employee_name") or "").strip()
            sender_phone = (data.get("sender_phone") or "").strip()
            principal_name = (data.get("principal_name") or "").strip()
            project_name = (data.get("project_name") or "").strip()
            payroll_cao_setting_id = None
            if relation_id:
                cursor.execute("SELECT name, phone FROM relations WHERE id = %s;", (relation_id,))
                row = cursor.fetchone()
                if row:
                    candidate_name = candidate_name or row[0] or ""
                    sender_phone = sender_phone or row[1] or ""
            if principal_id:
                cursor.execute("SELECT name FROM relations WHERE id = %s;", (principal_id,))
                row = cursor.fetchone()
                if row:
                    principal_name = principal_name or row[0] or ""
            if project_id:
                cursor.execute("SELECT title, payroll_cao_setting_id FROM vacancies WHERE id = %s;", (project_id,))
                row = cursor.fetchone()
                if row:
                    project_name = project_name or row[0] or ""
                    payroll_cao_setting_id = row[1]
            week_number = work_date.isocalendar().week
            day_keys = [
                "monday_hours",
                "tuesday_hours",
                "wednesday_hours",
                "thursday_hours",
                "friday_hours",
                "saturday_hours",
                "sunday_hours",
            ]
            parsed_fields = {
                "employee_name": {"value": candidate_name, "confidence": 100, "verified": True},
                "employee_phone": {"value": sender_phone, "confidence": 100, "verified": True},
                "date": {"value": work_date.strftime("%d-%m-%Y"), "confidence": 100, "verified": True},
                "work_date": {"value": work_date.isoformat(), "confidence": 100, "verified": True},
                "week_number": {"value": str(week_number), "confidence": 100, "verified": True},
                "principal_name": {"value": principal_name, "confidence": 100, "verified": True},
                "project_name": {"value": project_name, "confidence": 100, "verified": True},
                "total_hours": {"value": _format_number(hours), "confidence": 100, "verified": True},
                "remarks": {"value": (data.get("remarks") or "").strip(), "confidence": 100, "verified": True},
            }
            for index, key in enumerate(day_keys):
                parsed_fields[key] = {"value": _format_number(hours) if index == work_date.weekday() else "", "confidence": 100, "verified": True}
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
                    principal_name,
                    project_name,
                    work_date,
                    hours,
                    break_minutes,
                    selected_principal_id,
                    selected_project_id,
                    validated_at,
                    parsed_fields,
                    overall_confidence
                )
                VALUES (%s, %s, %s, %s, '', 'manual_entry', 'manual_entry', %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s, CASE WHEN %s = 'loon_te_berekenen' THEN NOW() ELSE NULL END, %s, 100)
                RETURNING id;
                """,
                (
                    candidate_name or "Handmatige invoer",
                    sender_phone or "onbekend",
                    (data.get("remarks") or "Handmatig ingevoerde uren").strip(),
                    f"handmatige-uren-{work_date.isoformat()}.manual",
                    status,
                    relation_id,
                    candidate_name,
                    candidate_name,
                    principal_name,
                    project_name,
                    work_date,
                    hours,
                    principal_id,
                    project_id,
                    status,
                    Json(parsed_fields),
                ),
            )
            timesheet_id = cursor.fetchone()[0]
            if status == "loon_te_berekenen":
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
    log_audit_event(
        action="Handmatige uren ingevoerd",
        entity_type="urenbriefje",
        entity_id=timesheet_id,
        entity_label=candidate_name or f"Urenbriefje {timesheet_id}",
        description=f"{_format_number(hours)} uur handmatig ingevoerd voor {work_date:%d-%m-%Y}.",
        status="Loon berekenen" if status == "loon_te_berekenen" else "Controle",
        metadata={
            "bron": "handmatige invoer",
            "status": status,
            "relation_id": relation_id,
            "principal_id": principal_id,
            "project_id": project_id,
            "project": project_name,
            "opdrachtgever": principal_name,
        },
    )
    return timesheet_id


def _payroll_period_totals(rows: list[dict]) -> dict:
    total_hours = sum(Decimal(str(row["total_hours"]).replace(",", ".")) for row in rows) if rows else Decimal("0")
    total_bookings = sum(int(row["booking_count"] or 0) for row in rows)
    total_days = sum(int(row["worked_days"] or 0) for row in rows)
    return {
        "employees": len(rows),
        "bookings": total_bookings,
        "days": total_days,
        "hours": _format_number(total_hours),
    }


def list_payroll_period_totals(period_id: int) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT employee_name,
                           total_worked_days,
                           total_worked_hours,
                           total_vacation_hours,
                           total_sickness_hours,
                           total_rv_hours,
                           total_kv_hours,
                           total_holiday_hours,
                           total_km,
                           total_declarations,
                           total_net_advance,
                           already_received_net,
                           net_to_receive,
                           total_period_amount,
                           wkr_reimbursements,
                           status,
                           source
                    FROM payroll_period_totals
                    WHERE payroll_period_id = %s
                    ORDER BY employee_name;
                    """,
                    (period_id,),
                )
                return [
                    {
                        "employee_name": row[0],
                        "total_worked_days": _format_number(row[1]),
                        "total_worked_hours": _format_number(row[2]),
                        "total_vacation_hours": _format_number(row[3]),
                        "total_sickness_hours": _format_number(row[4]),
                        "total_rv_hours": _format_number(row[5]),
                        "total_kv_hours": _format_number(row[6]),
                        "total_holiday_hours": _format_number(row[7]),
                        "total_km": _format_number(row[8]),
                        "total_declarations": _format_money(row[9]),
                        "total_net_advance": _format_money(row[10]),
                        "already_received_net": _format_money(row[11]),
                        "net_to_receive": _format_money(row[12]),
                        "total_period_amount": _format_money(row[13]),
                        "wkr_reimbursements": _format_money(row[14]),
                        "status": row[15] or "concept",
                        "source": row[16] or "dashboard",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_payroll_sheet_candidates(limit: int = 250) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, phone, city, hourly_rate, notes, status
                    FROM relations
                    WHERE relation_type = 'candidate'
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'verwijderd')
                    ORDER BY name
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "id": row[0],
                        "name": row[1],
                        "phone": row[2] or "",
                        "city": row[3] or "",
                        "hourly_rate": row[4] or "",
                        "notes": row[5] or "",
                        "status": row[6] or "",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_payroll_workbook_overrides(period_id: int) -> dict[tuple[str, str, str], dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tab_label,
                           row_key,
                           column_key,
                           original_value,
                           previous_value,
                           value,
                           updated_at
                    FROM payroll_workbook_cell_overrides
                    WHERE payroll_period_id = %s;
                    """,
                    (period_id,),
                )
                return {
                    (row[0], row[1], row[2]): {
                        "original_value": row[3] or "",
                        "previous_value": row[4] or "",
                        "value": row[5] or "",
                        "updated_at": row[6].strftime("%d-%m-%Y %H:%M") if row[6] else "",
                    }
                    for row in cursor.fetchall()
                }
    except Exception:
        return {}


def apply_payroll_workbook_overrides(period_id: int, tabs: list[dict]) -> None:
    overrides = list_payroll_workbook_overrides(period_id)
    for tab in tabs:
        for row_index, row in enumerate(tab.get("rows", []), start=1):
            row_key = _payroll_workbook_row_key(row, row_index)
            row["_row_key"] = row_key
            row["_mutations"] = {}
            for column in tab.get("columns", []):
                key = (tab.get("label"), row_key, column.get("key"))
                override = overrides.get(key)
                if override:
                    row[column["key"]] = override["value"]
                    row["_mutations"][column["key"]] = override


def save_payroll_workbook_cell(period_id: int, payload: dict) -> dict:
    _ensure_dashboard_tables_for_read()
    tab_label = str(payload.get("tab_label") or "").strip()
    row_key = str(payload.get("row_key") or "").strip()
    employee_name = str(payload.get("employee_name") or "").strip()
    relation_id = _int_or_none(payload.get("relation_id"))
    column_key = str(payload.get("column_key") or "").strip()
    column_label = str(payload.get("column_label") or column_key).strip()
    original_value = str(payload.get("original_value") or "").strip()
    previous_value = str(payload.get("previous_value") or original_value).strip()
    value = str(payload.get("value") or "").strip()
    if not tab_label or not row_key or not column_key:
        return {"ok": False, "error": "Tabblad, rij of kolom ontbreekt."}
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payroll_workbook_cell_overrides (
                    payroll_period_id, tab_label, row_key, employee_name, relation_id,
                    column_key, column_label, original_value, previous_value, value, reviewed_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Admin')
                ON CONFLICT (payroll_period_id, tab_label, row_key, column_key)
                DO UPDATE SET
                    previous_value = payroll_workbook_cell_overrides.value,
                    value = EXCLUDED.value,
                    employee_name = EXCLUDED.employee_name,
                    relation_id = EXCLUDED.relation_id,
                    column_label = EXCLUDED.column_label,
                    reviewed_by = 'Admin',
                    updated_at = NOW()
                RETURNING previous_value, value, updated_at;
                """,
                (
                    period_id,
                    tab_label,
                    row_key,
                    employee_name,
                    relation_id,
                    column_key,
                    column_label,
                    original_value,
                    previous_value,
                    value,
                ),
            )
            row = cursor.fetchone()
        conn.commit()
    log_audit_event(
        action="Payroll cel aangepast",
        entity_type="payroll_period",
        entity_id=period_id,
        entity_label=f"{tab_label} - {employee_name or row_key}",
        description=f"{column_label}: '{row[0] or ''}' gewijzigd naar '{row[1] or ''}'.",
        status="mutatie",
        metadata={
            "tab_label": tab_label,
            "row_key": row_key,
            "employee_name": employee_name,
            "relation_id": relation_id,
            "column_key": column_key,
            "column_label": column_label,
            "previous_value": row[0] or "",
            "value": row[1] or "",
        },
    )
    return {
        "ok": True,
        "previous_value": row[0] or "",
        "value": row[1] or "",
        "updated_at": row[2].strftime("%d-%m-%Y %H:%M") if row[2] else "",
    }


def _payroll_workbook_row_key(row: dict, row_index: int) -> str:
    relation_id = row.get("relation_id")
    if relation_id:
        return f"relation:{relation_id}"
    name = str(row.get("employee_name") or "").strip().lower()
    return f"name:{name}" if name else f"row:{row_index}"


def list_payroll_import_logs(period_id: int, limit: int = 20) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT filename, status, sheet_names, mapped_fields, formulas, warnings, created_at
                    FROM payroll_import_logs
                    WHERE payroll_period_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (period_id, limit),
                )
                return [
                    {
                        "filename": row[0],
                        "status": row[1],
                        "sheet_names": row[2] or [],
                        "mapped_fields": row[3] or {},
                        "formulas": row[4] or [],
                        "warnings": row[5] or [],
                        "created_at": row[6].strftime("%d-%m-%Y %H:%M") if row[6] else "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_payroll_calculation_rules(limit: int = 50) -> list[dict]:
    ensure_default_payroll_rules()
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT rule_key, name, category, expression, status, notes
                    FROM payroll_calculation_rules
                    ORDER BY category, name
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "rule_key": row[0],
                        "name": row[1],
                        "category": row[2],
                        "expression": row[3] or "",
                        "status": row[4],
                        "notes": row[5] or "",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_payroll_validation_results(period_id: int, limit: int = 100) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT employee_name, result_key, dashboard_value, excel_value, difference, status, details
                    FROM payroll_calculation_results
                    WHERE payroll_period_id = %s
                    ORDER BY employee_name, result_key
                    LIMIT %s;
                    """,
                    (period_id, limit),
                )
                return [
                    {
                        "employee_name": row[0],
                        "result_key": row[1],
                        "dashboard_value": _format_number(row[2]),
                        "excel_value": _format_number(row[3]),
                        "difference": _format_number(row[4]),
                        "status": row[5],
                        "details": row[6] or {},
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def ensure_default_payroll_rules() -> None:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                for rule in default_calculation_rules():
                    cursor.execute(
                        """
                        INSERT INTO payroll_calculation_rules
                            (rule_key, name, category, expression, status, source, notes)
                        VALUES (%s, %s, %s, %s, %s, 'dashboard', %s)
                        ON CONFLICT (rule_key) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            expression = EXCLUDED.expression,
                            status = EXCLUDED.status,
                            notes = EXCLUDED.notes,
                            updated_at = NOW();
                        """,
                        (
                            rule["rule_key"],
                            rule["name"],
                            rule["category"],
                            rule["expression"],
                            rule["status"],
                            rule["notes"],
                        ),
                    )
            conn.commit()
    except Exception:
        return


def record_payroll_excel_analysis(period_id: int, analysis: dict, imported_from: str = "dashboard_upload") -> None:
    _ensure_dashboard_tables_for_read()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payroll_import_logs
                    (payroll_period_id, filename, imported_from, status, sheet_names, mapped_fields, formulas, warnings)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    period_id,
                    analysis.get("filename") or "Excel import",
                    imported_from,
                    "geanalyseerd" if not analysis.get("warnings") else "controle_nodig",
                    Json(
                        {
                            "all": analysis.get("sheet_names", []),
                            "week_tabs": analysis.get("week_tabs", []),
                            "period_sheet": analysis.get("period_sheet"),
                            "payslip_sheet": analysis.get("payslip_sheet"),
                            "foundation_sheets": analysis.get("foundation_sheets", []),
                        }
                    ),
                    Json(analysis.get("mapped_fields", {})),
                    Json({"count": analysis.get("formula_count", 0), "samples": analysis.get("formulas", [])}),
                    Json(analysis.get("warnings", [])),
                ),
            )
        conn.commit()


def create_payroll_period(data: dict) -> int:
    _ensure_dashboard_tables_for_read()
    year = _int_or_none(data.get("year")) or date.today().year
    period_number = _int_or_none(data.get("period_number")) or 1
    if period_number < 1 or period_number > PAYROLL_PERIODS_PER_YEAR:
        raise ValueError(f"Een loonjaar heeft precies {PAYROLL_PERIODS_PER_YEAR} periodes.")
    start_date = _date_or_none(data.get("start_date")) or date.today()
    end_date = _date_or_none(data.get("end_date")) or start_date + timedelta(days=27)
    name = (data.get("name") or "").strip() or f"Periode {period_number} - {year}"
    status = (data.get("status") or "").strip() or "concept"
    notes = (data.get("notes") or "").strip()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payroll_periods (
                    year, period_number, name, start_date, end_date, status, notes,
                    created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (year, period_number)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    start_date = EXCLUDED.start_date,
                    end_date = EXCLUDED.end_date,
                    status = EXCLUDED.status,
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING id;
                """,
                (year, period_number, name, start_date, end_date, status, notes),
            )
            period_id = cursor.fetchone()[0]
            cursor.execute("DELETE FROM payroll_period_weeks WHERE payroll_period_id = %s;", (period_id,))
            for week_index in range(1, 5):
                week_start = start_date + timedelta(days=(week_index - 1) * 7)
                week_end = min(week_start + timedelta(days=6), end_date)
                cursor.execute(
                    """
                    INSERT INTO payroll_period_weeks (
                        payroll_period_id, week_index, week_number, start_date, end_date,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW());
                    """,
                    (period_id, week_index, week_start.isocalendar().week, week_start, week_end),
                )
            cursor.execute(
                """
                UPDATE project_time_bookings
                SET payroll_period_id = %s,
                    updated_at = NOW()
                WHERE work_date BETWEEN %s AND %s
                  AND payroll_period_id IS NULL;
                """,
                (period_id, start_date, end_date),
            )
        conn.commit()
    return period_id


def create_payroll_period_batch(data: dict) -> list[int]:
    defaults = get_payroll_period_defaults()
    period_number = _int_or_none(data.get("period_number")) or defaults["period_number"]
    requested_count = max(_int_or_none(data.get("period_count")) or 1, 1)
    period_count = min(requested_count, PAYROLL_PERIODS_PER_YEAR)
    start_date = _date_or_none(data.get("start_date")) or _date_or_none(defaults["start_date"]) or date.today()
    display_period_number = _int_or_none(data.get("display_period_number")) or defaults.get("display_period_number") or period_number
    year = start_date.year
    notes = (data.get("notes") or "").strip()
    status = (data.get("status") or "Open").strip() or "Open"

    available_numbers = _available_payroll_period_numbers(year, period_count)
    period_count = min(period_count, len(available_numbers))
    created_ids: list[int] = []
    for offset in range(period_count):
        current_number = available_numbers[offset] if offset < len(available_numbers) else period_number + offset
        current_display_number = display_period_number + offset
        current_start = start_date + timedelta(days=28 * offset)
        current_end = current_start + timedelta(days=27)
        current_data = {
            "year": year,
            "period_number": current_number,
            "name": _payroll_period_name(current_display_number, current_start, current_end),
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
            "status": status,
            "notes": notes,
        }
        created_ids.append(create_payroll_period(current_data))
    return created_ids


def _available_payroll_period_numbers(year: int, count: int) -> list[int]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT period_number
                    FROM payroll_periods
                    WHERE year = %s
                    ORDER BY period_number;
                    """,
                    (year,),
                )
                used_numbers = {int(number or 0) for (number,) in cursor.fetchall()}
    except Exception:
        used_numbers = set()
    numbers: list[int] = []
    candidate = 1
    while len(numbers) < count and candidate <= PAYROLL_PERIODS_PER_YEAR:
        if candidate not in used_numbers:
            numbers.append(candidate)
        candidate += 1
    return numbers


def archive_payroll_period(period_id: int, archived: bool = True) -> None:
    if not period_id:
        return
    _ensure_dashboard_tables_for_read()
    new_status = "Archief" if archived else "Open"
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payroll_periods
                SET status = %s, updated_at = NOW()
                WHERE id = %s;
                """,
                (new_status, period_id),
            )
        conn.commit()


def delete_payroll_period(period_id: int) -> None:
    if not period_id:
        return
    _ensure_dashboard_tables_for_read()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE project_time_bookings
                SET payroll_period_id = NULL,
                    updated_at = NOW()
                WHERE payroll_period_id = %s;
                """,
                (period_id,),
            )
            cursor.execute(
                """
                DELETE FROM payroll_periods
                WHERE id = %s;
                """,
                (period_id,),
            )
        conn.commit()


def update_payroll_period_status(period_id: int, status: str) -> None:
    if not period_id:
        return
    _ensure_dashboard_tables_for_read()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payroll_periods
                SET status = %s, updated_at = NOW()
                WHERE id = %s;
                """,
                (status, period_id),
            )
        conn.commit()


def _payroll_period_name(period_number: int, start_date: date, end_date: date) -> str:
    return f"Periode {period_number:02d} {start_date:%d/%m} - {end_date:%d/%m}"


def _apply_period_display_numbers(periods: list[dict]) -> None:
    grouped: dict[int, list[dict]] = {}
    for period in periods:
        grouped.setdefault(period["year"], []).append(period)
    for year_periods in grouped.values():
        ordered = sorted(
            year_periods,
            key=lambda item: datetime.strptime(item["start_date"], "%d-%m-%Y") if item["start_date"] != "-" else datetime.min,
        )
        for display_number, period in enumerate(ordered, start=1):
            period["display_period_number"] = display_number
            start_date = datetime.strptime(period["start_date"], "%d-%m-%Y").date() if period["start_date"] != "-" else None
            end_date = datetime.strptime(period["end_date"], "%d-%m-%Y").date() if period["end_date"] != "-" else None
            if start_date and end_date:
                period["name"] = _payroll_period_name(display_number, start_date, end_date)


def _attach_period_weeks(cursor, periods: list[dict]) -> None:
    period_ids = [period["id"] for period in periods]
    if not period_ids:
        return
    cursor.execute(
        """
        SELECT payroll_period_id, week_index, week_number, start_date, end_date
        FROM payroll_period_weeks
        WHERE payroll_period_id = ANY(%s)
        ORDER BY payroll_period_id, week_index;
        """,
        (period_ids,),
    )
    period_map = {period["id"]: period for period in periods}
    for row in cursor.fetchall():
        period = period_map.get(row[0])
        if not period:
            continue
        period["weeks"].append(
            {
                "week_index": row[1],
                "week_number": row[2],
                "start_date": row[3].strftime("%d-%m-%Y") if row[3] else "-",
                "end_date": row[4].strftime("%d-%m-%Y") if row[4] else "-",
                "booking_count": 0,
                "project_count": 0,
                "total_hours": "0",
            }
        )
    cursor.execute(
        """
        SELECT pw.payroll_period_id,
               pw.week_index,
               COUNT(wi.id) AS booking_count,
               COUNT(DISTINCT COALESCE(wi.selected_project_id, b.project_id)) AS project_count,
               COALESCE(
                   SUM(
                       COALESCE(
                           wi.hours,
                           b.hours,
                           CASE
                               WHEN COALESCE(wi.parsed_fields->'total_hours'->>'value', '') ~ '^[0-9]+([,.][0-9]+)?$'
                               THEN REPLACE(wi.parsed_fields->'total_hours'->>'value', ',', '.')::numeric
                               ELSE 0
                           END
                       )
                   ),
                   0
               ) AS total_hours
        FROM payroll_period_weeks pw
        LEFT JOIN whatsapp_timesheet_inbox wi
            ON LOWER(REPLACE(COALESCE(wi.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
           AND wi.deleted_at IS NULL
           AND wi.archived_at IS NULL
           AND COALESCE(wi.work_date, wi.received_at::date) BETWEEN pw.start_date AND pw.end_date
        LEFT JOIN project_time_bookings b
            ON b.timesheet_inbox_id = wi.id
           AND LOWER(REPLACE(COALESCE(b.status, ''), ' ', '_')) IN ('loon_te_berekenen', 'loon_berekenen', 'loon', 'doorgestuurd_naar_loonadministratie', 'verwerkt', 'processed')
        WHERE pw.payroll_period_id = ANY(%s)
        GROUP BY pw.payroll_period_id, pw.week_index
        ORDER BY pw.payroll_period_id, pw.week_index;
        """,
        (period_ids,),
    )
    for period_id, week_index, booking_count, project_count, total_hours in cursor.fetchall():
        period = period_map.get(period_id)
        if not period:
            continue
        week = next((item for item in period["weeks"] if item["week_index"] == week_index), None)
        if not week:
            continue
        week["booking_count"] = booking_count or 0
        week["project_count"] = project_count or 0
        week["total_hours"] = _format_number(total_hours)


def _attach_project_bookings(cursor, projects: list[dict], per_project: int = 5) -> None:
    project_ids = [project["id"] for project in projects]
    if not project_ids:
        return
    cursor.execute(
        """
        SELECT *
        FROM (
            SELECT b.project_id,
                   b.id,
                   b.timesheet_inbox_id,
                   b.relation_id,
                   b.principal_id,
                   COALESCE(r.name, w.employee_name, w.matched_candidate_name, ''),
                   b.work_date,
                   b.hours,
                   b.status,
                   b.payroll_cao_setting_id,
                   c.name,
                   b.updated_at,
                   ROW_NUMBER() OVER (
                       PARTITION BY b.project_id
                       ORDER BY b.work_date DESC NULLS LAST, b.updated_at DESC, b.id DESC
                   ) AS row_number
            FROM project_time_bookings b
            LEFT JOIN relations r
                ON r.id = b.relation_id
            LEFT JOIN whatsapp_timesheet_inbox w
                ON w.id = b.timesheet_inbox_id
            LEFT JOIN payroll_cao_settings c
                ON c.id = b.payroll_cao_setting_id
            WHERE b.project_id = ANY(%s)
        ) ranked_bookings
        WHERE row_number <= %s
        ORDER BY project_id, work_date DESC NULLS LAST, updated_at DESC, id DESC;
        """,
        (project_ids, per_project),
    )
    project_map = {project["id"]: project for project in projects}
    for row in cursor.fetchall():
        project_id = row[0]
        project = project_map.get(project_id)
        if not project:
            continue
        project["recent_bookings"].append(
            {
                "id": row[1],
                "timesheet_inbox_id": row[2],
                "relation_id": row[3],
                "principal_id": row[4],
                "employee_name": row[5] or "Onbekend",
                "work_date": row[6].strftime("%d-%m-%Y") if row[6] else "-",
                "hours": _format_number(row[7]),
                "status": row[8] or "",
                "payroll_cao_setting_id": row[9],
                "cao_name": row[10] or "Nog niet gekoppeld",
                "updated_at": row[11].strftime("%d-%m-%Y %H:%M") if row[11] else "-",
            }
        )


def list_payroll_running_balances(limit: int = 200) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.id,
                           a.relation_id,
                           r.name,
                           a.balance_type,
                           a.balance_label,
                           a.balance_year,
                           a.annual_limit,
                           COALESCE(SUM(m.amount), 0) AS current_balance,
                           COUNT(m.id) AS mutation_count,
                           MAX(m.mutation_date) AS last_mutation_date,
                           a.status,
                           a.source
                    FROM payroll_running_balance_accounts a
                    JOIN relations r ON r.id = a.relation_id
                    LEFT JOIN payroll_running_balance_mutations m ON m.account_id = a.id
                    WHERE COALESCE(a.status, 'active') <> 'archived'
                    GROUP BY a.id, a.relation_id, r.name, a.balance_type, a.balance_label,
                             a.balance_year, a.annual_limit, a.status, a.source
                    ORDER BY r.name ASC,
                             CASE a.balance_type
                                 WHEN 'wkr' THEN 1
                                 WHEN 'loan_advance' THEN 2
                                 WHEN 'choice_budget' THEN 3
                                 ELSE 4
                             END
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        return [_payroll_running_balance_row(row) for row in rows]
    except Exception:
        return []


def list_relation_payroll_running_balances(relation_id: int, limit: int = 25) -> list[dict]:
    if not relation_id:
        return []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.id,
                           a.relation_id,
                           r.name,
                           a.balance_type,
                           a.balance_label,
                           a.balance_year,
                           a.annual_limit,
                           COALESCE(SUM(m.amount), 0) AS current_balance,
                           COUNT(m.id) AS mutation_count,
                           MAX(m.mutation_date) AS last_mutation_date,
                           a.status,
                           a.source
                    FROM payroll_running_balance_accounts a
                    JOIN relations r ON r.id = a.relation_id
                    LEFT JOIN payroll_running_balance_mutations m ON m.account_id = a.id
                    WHERE a.relation_id = %s
                      AND COALESCE(a.status, 'active') <> 'archived'
                    GROUP BY a.id, a.relation_id, r.name, a.balance_type, a.balance_label,
                             a.balance_year, a.annual_limit, a.status, a.source
                    ORDER BY CASE a.balance_type
                                 WHEN 'wkr' THEN 1
                                 WHEN 'loan_advance' THEN 2
                                 WHEN 'choice_budget' THEN 3
                                 ELSE 4
                             END,
                             a.id DESC
                    LIMIT %s;
                    """,
                    (relation_id, limit),
                )
                rows = cursor.fetchall()
        return [_payroll_running_balance_row(row) for row in rows]
    except Exception:
        return []


def _payroll_running_balance_row(row) -> dict:
    return {
        "id": row[0],
        "relation_id": row[1],
        "employee_name": row[2] or "Onbekend",
        "balance_type": row[3],
        "balance_label": row[4],
        "balance_year": row[5] or "doorlopend",
        "annual_limit": _format_money(row[6]) if row[6] is not None else "-",
        "current_balance": _format_money(row[7]),
        "raw_current_balance": Decimal(str(row[7] or 0)),
        "mutation_count": row[8] or 0,
        "last_mutation_date": row[9].strftime("%d-%m-%Y") if row[9] else "-",
        "status": _running_balance_status(row[3], row[6], row[7]),
        "source": row[11] or "dashboard",
    }


def list_relation_payroll_employee_arrangements(relation_id: int, limit: int = 5) -> list[dict]:
    if not relation_id:
        return []
    return [
        item
        for item in list_payroll_employee_arrangements(limit=500)
        if item.get("relation_id") == relation_id
    ][:limit]


def list_relation_payroll_period_settlements(relation_id: int, limit: int = 5) -> list[dict]:
    if not relation_id:
        return []
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.relation_id,
                           s.employee_name,
                           s.week_count,
                           s.total_worked_hours,
                           s.total_km,
                           s.net_wage_amount,
                           s.travel_amount,
                           s.day_allowance_amount,
                           s.advance_weeks_1_3,
                           s.week_4_amount,
                           s.total_period_amount,
                           s.payment_schedule,
                           s.settlement_status,
                           s.status_details,
                           p.year,
                           p.period_number,
                           p.name
                    FROM payroll_period_settlements s
                    JOIN payroll_periods p ON p.id = s.payroll_period_id
                    WHERE s.relation_id = %s
                    ORDER BY p.year DESC, p.period_number DESC, s.id DESC
                    LIMIT %s;
                    """,
                    (relation_id, limit),
                )
                rows = cursor.fetchall()
        return [_payroll_period_settlement_row(row) for row in rows]
    except Exception:
        return []


def _payroll_period_settlement_row(row) -> dict:
    return {
        "relation_id": row[0],
        "employee_name": row[1] or "Onbekend",
        "week_count": row[2] or 0,
        "worked_hours": _format_number(row[3]),
        "total_km": _format_number(row[4]),
        "net_wage_amount": _format_money(row[5]),
        "travel_amount": _format_money(row[6]),
        "day_allowance_amount": _format_money(row[7]),
        "advance_weeks_1_3": _format_money(row[8]),
        "week_4_amount": _format_money(row[9]),
        "net_period_total": _format_money(row[10]),
        "payment_schedule": "4-wekelijks" if row[11] == "four_weekly" else "wekelijks",
        "status_label": row[12] or "concept",
        "status_details": row[13] or {},
        "period_label": f"{row[14]} P{row[15]}" if row[14] and row[15] else row[16] or "Periode",
        "period_name": row[16] or "",
    }


def get_relation_payroll_context(relation_id: int | None) -> dict:
    if not relation_id:
        return {"arrangements": [], "current_arrangement": None, "balances": [], "settlements": []}
    arrangements = list_relation_payroll_employee_arrangements(relation_id)
    return {
        "arrangements": arrangements,
        "current_arrangement": arrangements[0] if arrangements else None,
        "balances": list_relation_payroll_running_balances(relation_id),
        "settlements": list_relation_payroll_period_settlements(relation_id),
    }


def _running_balance_status(balance_type: str, annual_limit, current_balance) -> str:
    if balance_type != "wkr" or annual_limit in (None, 0):
        return "actief"
    limit = Decimal(str(annual_limit))
    current = Decimal(str(current_balance or 0))
    if current > limit:
        return "boven maximum"
    if current >= limit * Decimal("0.9"):
        return "let op"
    return "actief"


def list_payroll_employee_arrangements(limit: int = 100) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.id,
                           a.relation_id,
                           r.name,
                           a.valid_from_year,
                           a.valid_from_period_number,
                           a.valid_until_year,
                           a.valid_until_period_number,
                           a.cao_branch,
                           a.phase,
                           a.pension_scheme,
                           a.contract_hours_4w,
                           a.days_right_code,
                           a.scale_code,
                           a.function_name,
                           a.gross_hourly_wage,
                           a.net_base_40h,
                           a.vacation_rate_40h,
                           a.sickness_rate_40h,
                           a.holiday_rate_40h,
                           a.payment_schedule,
                           a.company_car,
                           a.license_plate,
                           a.health_insurance_eligible,
                           a.status,
                           a.source,
                           COALESCE(right_counts.right_count, 0),
                           COALESCE(allowance_counts.allowance_count, 0),
                           a.updated_at
                    FROM payroll_employee_arrangements a
                    JOIN relations r ON r.id = a.relation_id
                    LEFT JOIN (
                        SELECT arrangement_id, COUNT(*) AS right_count
                        FROM payroll_employee_rights
                        GROUP BY arrangement_id
                    ) right_counts ON right_counts.arrangement_id = a.id
                    LEFT JOIN (
                        SELECT arrangement_id, COUNT(*) AS allowance_count
                        FROM payroll_employee_allowances
                        GROUP BY arrangement_id
                    ) allowance_counts ON allowance_counts.arrangement_id = a.id
                    WHERE COALESCE(a.status, 'concept') <> 'archief'
                    ORDER BY a.valid_from_year DESC,
                             a.valid_from_period_number DESC,
                             r.name ASC,
                             a.id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "id": row[0],
                        "relation_id": row[1],
                        "employee_name": row[2] or "Onbekend",
                        "valid_from": f"{row[3]} / P{row[4]}",
                        "valid_until": f"{row[5]} / P{row[6]}" if row[5] and row[6] else "Doorlopend",
                        "cao_branch": row[7] or "bouwplaats",
                        "phase": row[8] or "-",
                        "pension_scheme": row[9] or "-",
                        "contract_hours_4w": _format_number(row[10]) if row[10] is not None else "-",
                        "days_right_code": row[11] or "-",
                        "scale_code": row[12] or "-",
                        "function_name": row[13] or "-",
                        "gross_hourly_wage": _format_money(row[14]) if row[14] is not None else "-",
                        "net_base_40h": _format_money(row[15]) if row[15] is not None else "-",
                        "vacation_rate_40h": _format_money(row[16]) if row[16] is not None else "-",
                        "sickness_rate_40h": _format_money(row[17]) if row[17] is not None else "-",
                        "holiday_rate_40h": _format_money(row[18]) if row[18] is not None else "-",
                        "payment_schedule": "4-wekelijks" if row[19] == "four_weekly" else "wekelijks",
                        "company_car": bool(row[20]),
                        "license_plate": row[21] or "-",
                        "health_insurance_eligible": bool(row[22]),
                        "status": row[23] or "concept",
                        "source": row[24] or "dashboard",
                        "right_count": row[25] or 0,
                        "allowance_count": row[26] or 0,
                        "updated_at": row[27].strftime("%d-%m-%Y %H:%M") if row[27] else "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def get_payroll_parameter_values(year: int, period_number: int, branch: str = "build") -> dict[str, Decimal | str | None]:
    branch_key = "uta_value" if str(branch).lower() == "uta" else "build_value"
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT ON (p.parameter_key)
                           p.parameter_key,
                           p.unit,
                           v.build_value,
                           v.uta_value,
                           v.text_value
                    FROM payroll_parameters p
                    JOIN payroll_parameter_versions v
                        ON v.parameter_id = p.id
                    WHERE COALESCE(p.status, 'active') = 'active'
                      AND COALESCE(v.status, 'active') = 'active'
                      AND (v.year = %s OR v.year IS NULL)
                      AND (v.period_number <= %s OR v.period_number IS NULL)
                    ORDER BY p.parameter_key,
                             v.year DESC NULLS LAST,
                             v.period_number DESC NULLS LAST,
                             v.id DESC;
                    """,
                    (year, period_number),
                )
                rows = cursor.fetchall()
        values = {}
        for key, _unit, build_value, uta_value, text_value in rows:
            numeric_value = uta_value if branch_key == "uta_value" else build_value
            if numeric_value is None and branch_key == "uta_value":
                numeric_value = build_value
            if numeric_value is None and branch_key == "build_value":
                numeric_value = uta_value
            values[key] = Decimal(str(numeric_value)) if numeric_value is not None else text_value
        return values
    except Exception:
        return {}


def list_payroll_parameters(limit: int = 200) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT p.id,
                           p.parameter_key,
                           p.name,
                           p.category,
                           p.unit,
                           p.value_type,
                           p.applies_to,
                           p.source_reference,
                           p.description,
                           p.status,
                           v.year,
                           v.period_number,
                           v.build_value,
                           v.uta_value,
                           v.text_value,
                           COALESCE(v.source_reference, p.source_reference),
                           v.notes,
                           v.status
                    FROM payroll_parameters p
                    LEFT JOIN payroll_parameter_versions v
                        ON v.parameter_id = p.id
                    WHERE COALESCE(p.status, 'active') <> 'archived'
                    ORDER BY
                        p.category,
                        p.name,
                        v.year NULLS LAST,
                        v.period_number NULLS LAST,
                        v.id NULLS LAST
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
        parameters: dict[int, dict] = {}
        for row in rows:
            item = parameters.setdefault(
                row[0],
                {
                    "id": row[0],
                    "parameter_key": row[1],
                    "name": row[2],
                    "category": row[3],
                    "unit": row[4],
                    "value_type": row[5],
                    "applies_to": row[6],
                    "source_reference": row[7] or "",
                    "description": row[8] or "",
                    "status": row[9] or "active",
                    "versions": [],
                },
            )
            if row[10] is not None or row[11] is not None:
                item["versions"].append(
                    {
                        "year": row[10] or "-",
                        "period_number": row[11] or "-",
                        "build_value": _format_parameter_value(row[12], row[4]),
                        "uta_value": _format_parameter_value(row[13], row[4]),
                        "text_value": row[14] or "",
                        "source_reference": row[15] or "",
                        "notes": row[16] or "",
                        "status": row[17] or "active",
                    }
                )
        return list(parameters.values())
    except Exception:
        return []


def _format_parameter_value(value, unit: str = "") -> str:
    if value is None:
        return "-"
    decimal_value = Decimal(str(value))
    if unit == "percentage":
        return f"{(decimal_value * Decimal('100')).normalize()}%"
    if unit.startswith("euro"):
        return _format_money(decimal_value)
    if decimal_value == decimal_value.to_integral():
        return str(int(decimal_value))
    return _format_number(decimal_value)


def list_cao_settings(limit: int = 25) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id,
                           name,
                           version_label,
                           effective_from,
                           effective_until,
                           standard_week_hours,
                           overtime_after_hours,
                           weekday_overtime_percent,
                           saturday_percent,
                           sunday_percent,
                           holiday_percent,
                           travel_cost_per_km,
                           default_hourly_wage,
                           status,
                           source,
                           notes,
                           updated_at
                    FROM payroll_cao_settings
                    ORDER BY
                        CASE WHEN status = 'actief' THEN 0 ELSE 1 END,
                        effective_from DESC NULLS LAST,
                        updated_at DESC,
                        id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "id": row[0],
                        "name": row[1],
                        "version_label": row[2] or "",
                        "effective_from": row[3].strftime("%d-%m-%Y") if row[3] else "-",
                        "effective_from_input": row[3].strftime("%Y-%m-%d") if row[3] else "",
                        "effective_until": row[4].strftime("%d-%m-%Y") if row[4] else "-",
                        "effective_until_input": row[4].strftime("%Y-%m-%d") if row[4] else "",
                        "standard_week_hours": row[5],
                        "overtime_after_hours": row[6],
                        "weekday_overtime_percent": row[7],
                        "saturday_percent": row[8],
                        "sunday_percent": row[9],
                        "holiday_percent": row[10],
                        "travel_cost_per_km": row[11],
                        "default_hourly_wage": row[12],
                        "status": row[13] or "concept",
                        "source": row[14] or "manual",
                        "notes": row[15] or "",
                        "updated_at": row[16].strftime("%d-%m-%Y %H:%M") if row[16] else "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def get_cao_setting(setting_id: int | None) -> dict | None:
    if not setting_id:
        return None
    return next((item for item in list_cao_settings(limit=200) if item["id"] == setting_id), None)


def create_cao_setting(data: dict) -> int:
    _ensure_dashboard_tables_for_read()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO payroll_cao_settings (
                    name,
                    version_label,
                    effective_from,
                    effective_until,
                    standard_week_hours,
                    overtime_after_hours,
                    weekday_overtime_percent,
                    saturday_percent,
                    sunday_percent,
                    holiday_percent,
                    travel_cost_per_km,
                    default_hourly_wage,
                    status,
                    source,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual', %s, NOW(), NOW())
                RETURNING id;
                """,
                (
                    _empty_to_none(data.get("name")) or "CAO instelling",
                    _empty_to_none(data.get("version_label")),
                    _empty_to_none(data.get("effective_from")),
                    _empty_to_none(data.get("effective_until")),
                    _number_or_none(data.get("standard_week_hours")),
                    _number_or_none(data.get("overtime_after_hours")),
                    _number_or_none(data.get("weekday_overtime_percent")),
                    _number_or_none(data.get("saturday_percent")),
                    _number_or_none(data.get("sunday_percent")),
                    _number_or_none(data.get("holiday_percent")),
                    _number_or_none(data.get("travel_cost_per_km")),
                    _number_or_none(data.get("default_hourly_wage")),
                    _empty_to_none(data.get("status")) or "concept",
                    _empty_to_none(data.get("notes")),
                ),
            )
            setting_id = cursor.fetchone()[0]
        conn.commit()
    return setting_id


def update_cao_setting(setting_id: int, data: dict) -> None:
    _ensure_dashboard_tables_for_read()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE payroll_cao_settings
                SET name = %s,
                    version_label = %s,
                    effective_from = %s,
                    effective_until = %s,
                    standard_week_hours = %s,
                    overtime_after_hours = %s,
                    weekday_overtime_percent = %s,
                    saturday_percent = %s,
                    sunday_percent = %s,
                    holiday_percent = %s,
                    travel_cost_per_km = %s,
                    default_hourly_wage = %s,
                    status = %s,
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s;
                """,
                (
                    _empty_to_none(data.get("name")) or "CAO instelling",
                    _empty_to_none(data.get("version_label")),
                    _empty_to_none(data.get("effective_from")),
                    _empty_to_none(data.get("effective_until")),
                    _number_or_none(data.get("standard_week_hours")),
                    _number_or_none(data.get("overtime_after_hours")),
                    _number_or_none(data.get("weekday_overtime_percent")),
                    _number_or_none(data.get("saturday_percent")),
                    _number_or_none(data.get("sunday_percent")),
                    _number_or_none(data.get("holiday_percent")),
                    _number_or_none(data.get("travel_cost_per_km")),
                    _number_or_none(data.get("default_hourly_wage")),
                    _empty_to_none(data.get("status")) or "concept",
                    _empty_to_none(data.get("notes")),
                    setting_id,
                ),
            )
        conn.commit()


def list_tickets(limit: int = 25) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT title, sender_name, channel, status, priority, category
                    FROM tickets
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return [
                    {
                        "title": row[0],
                        "sender": row[1] or "-",
                        "channel": row[2],
                        "status": row[3],
                        "priority": row[4],
                        "category": row[5] or "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_vacancies(limit: int = 30, query: str = "", status: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                filters = []
                if query:
                    filters.append(
                        """
                        (
                           title ILIKE %s
                           OR reference_number ILIKE %s
                           OR status ILIKE %s
                           OR owner ILIKE %s
                           OR relation_name ILIKE %s
                           OR location ILIKE %s
                        )
                        """
                    )
                    like_query = f"%{query}%"
                    params.extend([like_query] * 6)
                if status:
                    filters.append("status = %s")
                    params.append(status)
                where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
                params.append(limit)
                cursor.execute(
                    f"""
                    SELECT id, title, reference_number, status, owner, relation_name,
                           location, publication_status, applicant_count,
                           website_enabled, indeed_enabled
                    FROM vacancies
                    {where_clause}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                return [
                    {
                        "id": row[0],
                        "title": row[1],
                        "reference_number": row[2] or "-",
                        "status": row[3] or "Concept",
                        "owner": row[4] or "-",
                        "relation_name": row[5] or "-",
                        "location": row[6] or "-",
                        "publication_status": row[7],
                        "applicant_count": row[8],
                        "website_enabled": row[9],
                        "indeed_enabled": row[10],
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_vacancy_statuses() -> list[str]:
    defaults = ["Concept", "Lopend", "Open", "Controle", "Afgesloten", "OTYS"]
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT DISTINCT status
                    FROM vacancies
                    WHERE COALESCE(status, '') <> ''
                    ORDER BY status;
                    """
                )
                values = [row[0] for row in cursor.fetchall() if row[0]]
    except Exception:
        values = []

    return _unique_options([*defaults, *values])


def list_relation_status_counts(relation_type: str = "", query: str = "") -> list[dict]:
    relation_type = relation_type if relation_type in {"candidate", "principal"} else "candidate"
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                filters = ["relation_type = %s"]
                params = [relation_type]
                if query:
                    filters.append(
                        """(
                           name ILIKE %s OR contact_name ILIKE %s OR email ILIKE %s
                        OR phone ILIKE %s OR city ILIKE %s OR status ILIKE %s OR external_id ILIKE %s
                        )"""
                    )
                    search = f"%{query}%"
                    params.extend([search] * 7)
                cursor.execute(
                    f"""
                    SELECT COALESCE(NULLIF(status, ''), 'Geen status'), COUNT(*)
                    FROM relations
                    WHERE {' AND '.join(filters)}
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC, 1;
                    """,
                    tuple(params),
                )
                return [{"label": row[0], "count": row[1]} for row in cursor.fetchall()]
    except Exception:
        return []


def list_relation_tab_counts() -> dict:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT LOWER(relation_type), COUNT(*)
                    FROM relations
                    WHERE archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    GROUP BY LOWER(relation_type);
                    """
                )
                counts = {row[0]: row[1] for row in cursor.fetchall()}
        return {
            "candidates": counts.get("candidate", 0),
            "principals": counts.get("principal", 0),
        }
    except Exception:
        return {"candidates": 0, "principals": 0}


def list_vacancy_status_counts(query: str = "") -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                where_clause = ""
                if query:
                    where_clause = """
                    WHERE title ILIKE %s OR reference_number ILIKE %s OR owner ILIKE %s
                       OR relation_name ILIKE %s OR location ILIKE %s OR status ILIKE %s
                    """
                    search = f"%{query}%"
                    params.extend([search] * 6)
                cursor.execute(
                    f"""
                    SELECT COALESCE(NULLIF(status, ''), 'Geen status'), COUNT(*)
                    FROM vacancies
                    {where_clause}
                    GROUP BY 1
                    ORDER BY COUNT(*) DESC, 1;
                    """,
                    tuple(params),
                )
                return [{"label": row[0], "count": row[1]} for row in cursor.fetchall()]
    except Exception:
        return []


def _unique_options(values: list[str]) -> list[str]:
    seen = set()
    options = []
    for value in values:
        clean = str(value or "").strip()
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            options.append(clean)
    return options


def list_whatsapp_timesheets(limit: int = 100) -> list[dict]:
    try:
        _ensure_dashboard_tables_for_read()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT w.id,
                           w.sender_name,
                           w.sender_phone,
                           w.message_text,
                           w.media_filename,
                           w.media_path,
                           w.parse_source,
                           w.status,
                           COALESCE(r.name, c.name, w.matched_candidate_name, ''),
                           w.employee_name,
                           w.employee_address,
                           w.employee_postal_code,
                           w.employee_city,
                           w.principal_name,
                           w.project_name,
                           w.work_date,
                           w.hours,
                           w.break_minutes,
                           w.parsed_fields,
                           w.overall_confidence,
                           w.received_at,
                           w.selected_principal_id,
                           w.selected_project_id,
                           w.validated_at,
                           w.payroll_sent_at,
                           w.source_channel,
                           w.matched_relation_id
                    FROM whatsapp_timesheet_inbox w
                    LEFT JOIN relations r
                        ON r.id = w.matched_relation_id
                    LEFT JOIN candidates c
                        ON c.id = w.matched_candidate_id
                    WHERE w.deleted_at IS NULL
                      AND w.archived_at IS NULL
                    ORDER BY COALESCE(w.work_date, w.received_at::date) ASC NULLS LAST, w.received_at ASC NULLS LAST, w.id ASC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                rows = cursor.fetchall()
                return [_format_whatsapp_row(row) for row in rows]
    except Exception as exc:
        print(f"WHATSAPP_TIMESHEETS_LIST_ERROR: {type(exc).__name__}: {exc}")
        return []


def _format_whatsapp_row(row) -> dict:
    fields = row[18] or {}
    _cap_unverified_timesheet_numbers(fields)
    _ensure_total_check(fields)
    source_channel = (row[25] or "manual_upload").strip() or "manual_upload"
    source_labels = {
        "whatsapp": "WhatsApp",
        "email": "E-mail",
        "server_folder": "Servermap",
        "manual": "Handmatige verwerking",
        "manual_upload": "Handmatige verwerking",
    }
    return {
        "id": row[0],
        "sender_name": row[1] or "-",
        "sender_phone": row[2],
        "message_text": row[3] or "",
        "media_filename": row[4] or "",
        "media_path": row[5] or "",
        "parse_source": row[6] or "",
        "status": row[7],
        "matched_name": row[8] or "Geen match",
        "employee_name": row[9] or "",
        "employee_address": row[10] or "",
        "employee_postal_code": row[11] or "",
        "employee_city": row[12] or "",
        "principal_name": row[13] or "",
        "project_name": row[14] or "",
        "work_date": row[15],
        "work_date_display": row[15].strftime("%d-%m-%Y") if row[15] else "-",
        "work_date_sort": row[15].isoformat() if row[15] else "",
        "hours": row[16],
        "break_minutes": row[17],
        "parsed_fields": _confidence_fields(fields),
        "parsed_map": _confidence_map(fields),
        "overall_confidence": int(row[19] or 0),
        "received_at": row[20],
        "received_at_display": row[20].strftime("%d-%m-%Y %H:%M") if row[20] else "-",
        "received_at_sort": row[20].isoformat() if row[20] else "",
        "selected_principal_id": row[21],
        "selected_project_id": row[22],
        "validated_at": row[23],
        "payroll_sent_at": row[24],
        "source_channel": source_channel,
        "source_channel_label": source_labels.get(source_channel, "Handmatige verwerking"),
        "matched_relation_id": row[26],
    }


def _decimal_or_none(value):
    try:
        text = str(value or "").strip().replace("€", "").replace(" ", "").replace(",", ".")
        return Decimal(text) if text else None
    except Exception:
        return None


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _ensure_total_check(fields: dict) -> None:
    if "calculated_total_hours" not in fields or "total_hours_check" not in fields:
        _ensure_sum_check(
            fields,
            ("monday_hours", "tuesday_hours", "wednesday_hours", "thursday_hours", "friday_hours", "saturday_hours", "sunday_hours"),
            "total_hours",
            "calculated_total_hours",
            "total_hours_check",
            "uur",
            "totaal ontbreekt",
        )
    if "calculated_total_km" not in fields or "total_km_check" not in fields:
        _ensure_sum_check(
            fields,
            ("monday_km", "tuesday_km", "wednesday_km", "thursday_km", "friday_km", "saturday_km", "sunday_km"),
            "total_km",
            "calculated_total_km",
            "total_km_check",
            "km",
            "totaal km ontbreekt",
        )


def _cap_unverified_timesheet_numbers(fields: dict) -> None:
    critical_keys = (
        "monday_hours",
        "tuesday_hours",
        "wednesday_hours",
        "thursday_hours",
        "friday_hours",
        "saturday_hours",
        "sunday_hours",
        "total_hours",
        "calculated_total_hours",
        "total_hours_check",
        "monday_km",
        "tuesday_km",
        "wednesday_km",
        "thursday_km",
        "friday_km",
        "saturday_km",
        "sunday_km",
        "total_km",
        "calculated_total_km",
        "total_km_check",
    )
    for key in critical_keys:
        payload = fields.get(key)
        if not isinstance(payload, dict) or payload.get("verified"):
            continue
        if str(payload.get("value") or "").strip():
            payload["confidence"] = min(int(payload.get("confidence", 0) or 0), 60)
            fields[key] = payload


def _ensure_sum_check(
    fields: dict,
    day_keys: tuple[str, ...],
    total_key: str,
    calculated_key: str,
    check_key: str,
    unit: str,
    missing_message: str,
) -> None:
    day_keys = (
        *day_keys,
    )
    values = [_decimal_or_none((fields.get(key) or {}).get("value")) for key in day_keys]
    known_values = [value for value in values if value is not None]
    if not known_values:
        fields.setdefault(calculated_key, {"value": "", "confidence": 0})
        fields.setdefault(check_key, {"value": "", "confidence": 0})
        return
    calculated = sum(known_values, Decimal("0"))
    stated_total = _decimal_or_none((fields.get(total_key) or {}).get("value"))
    fields.setdefault(calculated_key, {"value": _format_decimal(calculated), "confidence": 98})
    if stated_total is None:
        fields.setdefault(check_key, {"value": missing_message, "confidence": 98})
    elif calculated == stated_total:
        fields.setdefault(check_key, {"value": "klopt", "confidence": 98})
    else:
        difference = abs(calculated - stated_total)
        fields.setdefault(check_key, {"value": f"verschil {_format_decimal(difference)} {unit}", "confidence": 90})


def _initials(name: str | None) -> str:
    parts = [part for part in (name or "").split() if part]
    if not parts:
        return "OB"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[-1][0]}".upper()


def _confidence_fields(fields: dict) -> list[dict]:
    labels = {
        "employee_name": "Medewerker",
        "employee_address": "Adres",
        "employee_city": "Plaats",
        "principal_name": "Opdrachtgever",
        "project_number": "Projectnummer",
        "project_name": "Project",
        "signer_name": "Naam ondertekenaar",
        "signer_phone": "Telefoon ondertekenaar",
        "work_number": "Werknummer",
        "week_number": "Weeknummer",
        "date": "Datum",
        "work_date": "Werkdatum",
        "hours": "Uren",
        "monday_hours": "Ma",
        "tuesday_hours": "Di",
        "wednesday_hours": "Wo",
        "thursday_hours": "Do",
        "friday_hours": "Vr",
        "saturday_hours": "Za",
        "sunday_hours": "Zo",
        "total_hours": "Totaal",
        "monday_km": "Km ma",
        "tuesday_km": "Km di",
        "wednesday_km": "Km wo",
        "thursday_km": "Km do",
        "friday_km": "Km vr",
        "saturday_km": "Km za",
        "sunday_km": "Km zo",
        "total_km": "Totaal km",
        "monday_code": "Code ma",
        "tuesday_code": "Code di",
        "wednesday_code": "Code wo",
        "thursday_code": "Code do",
        "friday_code": "Code vr",
        "saturday_code": "Code za",
        "sunday_code": "Code zo",
        "calculated_total_hours": "Berekend totaal",
        "total_hours_check": "Controle totaal",
        "calculated_total_km": "Berekend km totaal",
        "total_km_check": "Controle km totaal",
        "single_trip_km": "Km enkele reis",
        "absence_code": "Verzuimcode",
        "remarks": "Opmerking",
        "break_minutes": "Pauze",
        "signature": "Handtekening",
        "expenses": "Kosten",
        "parking_costs": "Parkeerkosten",
        "invoice_with_receipt": "Factureren met tegenbon",
        "client_signature": "Handtekening opdrachtgever",
    }
    return [
        {
            "key": key,
            "label": labels.get(key, key),
            "value": payload.get("value", ""),
            "confidence": int(payload.get("confidence", 0)),
        }
        for key, payload in fields.items()
    ]


def _confidence_map(fields: dict) -> dict:
    return {
        field["key"]: field
        for field in _confidence_fields(fields)
    }
