import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


def get_overview_data() -> dict:
    try:
        ensure_dashboard_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                counts = {}
                for table_name in ("vacancies", "tickets", "whatsapp_timesheet_inbox"):
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    counts[table_name] = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT relation_type, COUNT(*)
                    FROM relations
                    WHERE archived_at IS NULL
                      AND LOWER(COALESCE(status, '')) NOT IN ('archief', 'gearchiveerd', 'archived')
                    GROUP BY relation_type;
                    """
                )
                relation_counts = {row[0]: row[1] for row in cursor.fetchall()}
                counts["candidates"] = relation_counts.get("candidate", 0)
                counts["principals"] = relation_counts.get("principal", 0)

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
                    GROUP BY status;
                    """
                )
                whatsapp_statuses = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            "counts": counts,
            "recent": recent,
            "whatsapp_workflow": _whatsapp_workflow(whatsapp_statuses),
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
        }


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
        ensure_dashboard_tables()
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
        ensure_dashboard_tables()
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


def list_relations(limit: int = 50, query: str = "", relation_type: str = "") -> list[dict]:
    try:
        ensure_dashboard_tables()
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
                           street, house_number, house_number_addition, postal_code, country
                    FROM relations
                    {where_clause}
                    ORDER BY updated_at DESC, id DESC
                    LIMIT %s;
                    """,
                    tuple(params),
                )
                return [
                    {
                        "id": row[0],
                        "relation_type": row[1],
                        "type": "Opdrachtgever" if row[1] == "principal" else "Kandidaat",
                        "name": row[2],
                        "contact": row[5] or "-",
                        "email": row[4] or "-",
                        "phone": row[5] or "-",
                        "city": row[6] or "-",
                        "status": row[7] or "Nieuw",
                        "source": row[8] or "-",
                        "has_photo": bool(row[9]),
                        "initials": _initials(row[2]),
                        "street": row[10] or "-",
                        "house_number": row[11] or "",
                        "house_number_addition": row[12] or "",
                        "postal_code": row[13] or "-",
                        "country": row[14] or "-",
                    }
                    for row in cursor.fetchall()
                ]
    except Exception:
        return []


def list_principals(limit: int = 25, query: str = "") -> list[dict]:
    try:
        ensure_dashboard_tables()
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
        ensure_dashboard_tables()
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


def list_projects(limit: int = 100, query: str = "") -> list[dict]:
    try:
        ensure_dashboard_tables()
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
    projects = list_projects(limit=500)
    project = next((item for item in projects if item["id"] == project_id), None)
    if not project:
        return None
    project["bookings"] = list_project_time_bookings(project_id)
    return project


def list_project_time_bookings(project_id: int, limit: int = 250) -> list[dict]:
    try:
        ensure_dashboard_tables()
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
    ensure_dashboard_tables()
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


def list_payroll_periods(limit: int = 25) -> list[dict]:
    try:
        ensure_dashboard_tables()
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
                               COUNT(b.id) AS booking_count,
                               SUM(b.hours) AS total_hours
                        FROM payroll_periods p2
                        LEFT JOIN project_time_bookings b
                            ON b.payroll_period_id = p2.id
                            OR (b.payroll_period_id IS NULL AND b.work_date BETWEEN p2.start_date AND p2.end_date)
                        GROUP BY p2.id
                    ) b ON b.payroll_period_id = p.id
                    ORDER BY p.year DESC, p.period_number DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )
                periods = [
                    {
                        "id": row[0],
                        "year": row[1],
                        "period_number": row[2],
                        "name": row[3],
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
                _attach_period_weeks(cursor, periods)
                return periods
    except Exception:
        return []


def get_payroll_period(period_id: int | None) -> dict | None:
    if not period_id:
        return None
    period = next((item for item in list_payroll_periods(limit=200) if item["id"] == period_id), None)
    if period:
        period["payroll_rows"] = list_payroll_period_payroll(period_id)
        period["payroll_totals"] = _payroll_period_totals(period["payroll_rows"])
    return period


def list_payroll_period_payroll(period_id: int) -> list[dict]:
    try:
        ensure_dashboard_tables()
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
                    SELECT b.id,
                           b.relation_id,
                           COALESCE(r.name, w.employee_name, w.matched_candidate_name, 'Onbekend') AS employee_name,
                           COALESCE(c.name, 'Geen CAO') AS cao_name,
                           COALESCE(c.standard_week_hours, 40) AS standard_week_hours,
                           COALESCE(c.weekday_overtime_percent, 125) AS weekday_overtime_percent,
                           r.hourly_rate,
                           COALESCE(c.default_hourly_wage, 0) AS cao_hourly_wage,
                           COALESCE(v.title, w.project_name, '-') AS project_name,
                           COALESCE(p.name, w.principal_name, '-') AS principal_name,
                           b.work_date,
                           COALESCE(b.hours, 0) AS hours,
                           b.status
                    FROM project_time_bookings b
                    LEFT JOIN relations r
                        ON r.id = b.relation_id
                    LEFT JOIN relations p
                        ON p.id = b.principal_id
                    LEFT JOIN vacancies v
                        ON v.id = b.project_id
                    LEFT JOIN payroll_cao_settings c
                        ON c.id = b.payroll_cao_setting_id
                    LEFT JOIN whatsapp_timesheet_inbox w
                        ON w.id = b.timesheet_inbox_id
                    WHERE b.payroll_period_id = %s
                       OR (b.payroll_period_id IS NULL AND b.work_date BETWEEN %s AND %s)
                    ORDER BY employee_name, b.work_date, b.id;
                    """,
                    (period_id, start_date, end_date),
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
                        }
                    )
                return sorted(rows, key=lambda item: item["employee_name"])
    except Exception:
        return []


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


def create_payroll_period(data: dict) -> int:
    ensure_dashboard_tables()
    year = _int_or_none(data.get("year")) or date.today().year
    period_number = _int_or_none(data.get("period_number")) or 1
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
            }
        )


def _attach_project_bookings(cursor, projects: list[dict], per_project: int = 5) -> None:
    project_ids = [project["id"] for project in projects]
    if not project_ids:
        return
    cursor.execute(
        """
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
               b.updated_at
        FROM project_time_bookings b
        LEFT JOIN relations r
            ON r.id = b.relation_id
        LEFT JOIN whatsapp_timesheet_inbox w
            ON w.id = b.timesheet_inbox_id
        LEFT JOIN payroll_cao_settings c
            ON c.id = b.payroll_cao_setting_id
        WHERE b.project_id = ANY(%s)
        ORDER BY b.project_id, b.work_date DESC NULLS LAST, b.updated_at DESC, b.id DESC;
        """,
        (project_ids,),
    )
    project_map = {project["id"]: project for project in projects}
    counters = {project_id: 0 for project_id in project_ids}
    for row in cursor.fetchall():
        project_id = row[0]
        if counters.get(project_id, 0) >= per_project:
            continue
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
        counters[project_id] = counters.get(project_id, 0) + 1


def list_cao_settings(limit: int = 25) -> list[dict]:
    try:
        ensure_dashboard_tables()
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
    ensure_dashboard_tables()
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
    ensure_dashboard_tables()
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
        ensure_dashboard_tables()
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


def list_vacancies(limit: int = 30, query: str = "") -> list[dict]:
    try:
        ensure_dashboard_tables()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                params = []
                where_clause = ""
                if query:
                    where_clause = """
                    WHERE title ILIKE %s
                       OR reference_number ILIKE %s
                       OR status ILIKE %s
                       OR owner ILIKE %s
                       OR relation_name ILIKE %s
                       OR location ILIKE %s
                    """
                    like_query = f"%{query}%"
                    params.extend([like_query] * 6)
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


def list_whatsapp_timesheets(limit: int = 25) -> list[dict]:
    try:
        ensure_dashboard_tables()
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
                           w.source_channel
                    FROM whatsapp_timesheet_inbox w
                    LEFT JOIN relations r
                        ON r.id = w.matched_relation_id
                    LEFT JOIN candidates c
                        ON c.id = w.matched_candidate_id
                    WHERE w.deleted_at IS NULL
                      AND w.archived_at IS NULL
                    ORDER BY w.received_at DESC, w.id DESC
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
        "hours": row[16],
        "break_minutes": row[17],
        "parsed_fields": _confidence_fields(fields),
        "parsed_map": _confidence_map(fields),
        "overall_confidence": int(row[19] or 0),
        "received_at": row[20],
        "selected_principal_id": row[21],
        "selected_project_id": row[22],
        "validated_at": row[23],
        "payroll_sent_at": row[24],
        "source_channel": source_channel,
        "source_channel_label": source_labels.get(source_channel, "Handmatige verwerking"),
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
