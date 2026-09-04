from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from mimetypes import guess_type
from pathlib import Path
import re
from uuid import uuid4

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


INVOICE_EXPORT_DIR = Path("runtime/exports/invoicing")
INVOICE_DOCUMENT_DIR = Path("runtime/uploads/invoicing")
DEFAULT_FEE_PERCENT = Decimal("13.50")
FACTORING_FEE_PERCENT = Decimal("13.50")
DEFAULT_ADMIN_FEE = Decimal("8.50")
OLYMPUS_VAT_RATE = Decimal("21")
MONTHS_NL = (
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
)


def _decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    text = str(value or "").strip().replace("€", "").replace(" ", "")
    if not text:
        return default
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return default


def _money(value) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_text(value) -> str:
    amount = _money(value)
    sign = "-" if amount < 0 else ""
    whole, cents = f"{abs(amount):.2f}".split(".")
    return f"{sign}€ {int(whole):,}".replace(",", ".") + f",{cents}"


def _number_text(value) -> str:
    amount = _decimal(value)
    if amount == amount.to_integral():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _date_text(value) -> str:
    if not value:
        return "-"
    return f"{value.day} {MONTHS_NL[value.month - 1]} {value.year}"


def _parse_date(value: str | date | None) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError("Gebruik een geldige factuurdatum.")


def _ensure() -> None:
    ensure_dashboard_tables()


def _reportlab_dependencies():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    return colors, A4, canvas


def _run_row(cursor, run_id: int):
    cursor.execute(
        """
        SELECT id, year, week_number, invoice_date, status, created_at, updated_at
        FROM invoice_runs
        WHERE id = %s;
        """,
        (run_id,),
    )
    return cursor.fetchone()


def create_invoice_run(year: int, week_number: int, invoice_date: str | date) -> int:
    if not 1 <= int(week_number) <= 53:
        raise ValueError("Het kalenderweeknummer moet tussen 1 en 53 liggen.")
    invoice_date_value = _parse_date(invoice_date)
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO invoice_runs (year, week_number, invoice_date, status)
                VALUES (%s, %s, %s, 'concept')
                RETURNING id;
                """,
                (int(year), int(week_number), invoice_date_value),
            )
            run_id = cursor.fetchone()[0]
        conn.commit()
    return run_id


def create_invoice_agreement(data: dict) -> int:
    relation_id = int(data.get("relation_id") or 0)
    principal_id = int(data.get("principal_id") or 0)
    project_id = int(data.get("project_id") or 0)
    if not all((relation_id, principal_id, project_id)):
        raise ValueError("Kies een zzp'er, opdrachtgever en project voor de overeenkomst.")
    regime = "aangenomen werk" if str(data.get("regime") or "").strip().lower() in {"aangenomen", "aangenomen werk"} else "regie"
    hourly_rate = _money(data.get("hourly_rate")) if regime == "regie" else Decimal("0")
    if regime == "regie" and hourly_rate <= 0:
        raise ValueError("Vul het overeengekomen uurtarief in.")
    status = str(data.get("status") or "concept").strip().lower()
    if status not in {"concept", "verzonden", "getekend", "beeindigd"}:
        status = "concept"
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO invoice_agreements
                    (relation_id, principal_id, project_id, regime, hourly_rate, start_date, end_date, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, NULLIF(%s, '')::date, %s, %s)
                RETURNING id;
                """,
                (relation_id, principal_id, project_id, regime, hourly_rate, _parse_date(data.get("start_date")),
                 str(data.get("end_date") or "").strip(), status, str(data.get("notes") or "").strip()),
            )
            agreement_id = cursor.fetchone()[0]
        conn.commit()
    return agreement_id


def _agreement_row(cursor, agreement_id: int | str | None) -> dict | None:
    if not agreement_id:
        return None
    cursor.execute(
        """
        SELECT id, relation_id, principal_id, project_id, regime, hourly_rate, start_date, end_date, status, notes
        FROM invoice_agreements
        WHERE id = %s;
        """,
        (int(agreement_id),),
    )
    row = cursor.fetchone()
    if not row:
        return None
    keys = ("id", "relation_id", "principal_id", "project_id", "regime", "hourly_rate", "start_date", "end_date", "status", "notes")
    return dict(zip(keys, row))


def list_invoice_agreements() -> list[dict]:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.relation_id, a.principal_id, a.project_id, a.regime, a.hourly_rate,
                       a.start_date, a.end_date, a.status, a.notes,
                       COALESCE(z.name, ''), COALESCE(k.name, ''), COALESCE(v.title, ''),
                       COALESCE(v.reference_number, ''), COUNT(d.id)
                FROM invoice_agreements a
                LEFT JOIN relations z ON z.id = a.relation_id
                LEFT JOIN relations k ON k.id = a.principal_id
                LEFT JOIN vacancies v ON v.id = a.project_id
                LEFT JOIN invoice_documents d ON d.agreement_id = a.id
                GROUP BY a.id, z.name, k.name, v.title, v.reference_number
                ORDER BY CASE a.status WHEN 'getekend' THEN 0 WHEN 'verzonden' THEN 1 WHEN 'concept' THEN 2 ELSE 3 END,
                         a.start_date DESC, a.id DESC;
                """
            )
            rows = cursor.fetchall()
    agreements = []
    for row in rows:
        agreement = dict(zip((
            "id", "relation_id", "principal_id", "project_id", "regime", "hourly_rate", "start_date", "end_date", "status", "notes",
            "employee_name", "principal_name", "project_name", "project_reference", "document_count",
        ), row))
        agreement["hourly_rate_text"] = _money_text(agreement["hourly_rate"])
        agreement["start_date_text"] = _date_text(agreement["start_date"])
        agreement["status_label"] = {"concept": "Concept", "verzonden": "Verzonden", "getekend": "Getekend", "beeindigd": "Beeindigd"}.get(agreement["status"], agreement["status"])
        agreement["is_invoice_ready"] = agreement["status"] == "getekend"
        agreements.append(agreement)
    return agreements


def archive_invoice_run(run_id: int) -> None:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE invoice_runs SET status = 'archief', updated_at = NOW() WHERE id = %s RETURNING id;", (run_id,))
            if not cursor.fetchone():
                raise ValueError("Factuurrun niet gevonden.")
        conn.commit()


def restore_invoice_run(run_id: int) -> None:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE invoice_runs SET status = 'concept', updated_at = NOW() WHERE id = %s AND status = 'archief' RETURNING id;", (run_id,))
            if not cursor.fetchone():
                raise ValueError("Gearchiveerde factuurrun niet gevonden.")
        conn.commit()


def _lookup_names(cursor, relation_id, principal_id, project_id) -> dict:
    names = {
        "employee_name": "", "principal_name": "", "project_name": "", "project_reference": "",
        "employee_hourly_rate": "", "employee_payment_method": "",
    }
    if relation_id:
        cursor.execute(
            """
            SELECT name, COALESCE(hourly_rate, ''), COALESCE(invoice_payment_method, '')
            FROM relations WHERE id = %s AND relation_type = 'candidate';
            """,
            (relation_id,),
        )
        row = cursor.fetchone()
        if row:
            names["employee_name"] = row[0] or ""
            names["employee_hourly_rate"] = row[1] or ""
            names["employee_payment_method"] = row[2] or ""
    if principal_id:
        cursor.execute("SELECT name, COALESCE(external_id, '') FROM relations WHERE id = %s AND relation_type = 'principal';", (principal_id,))
        row = cursor.fetchone()
        if row:
            names["principal_name"] = row[0] or ""
    if project_id:
        cursor.execute("SELECT title, COALESCE(reference_number, ''), COALESCE(location, '') FROM vacancies WHERE id = %s;", (project_id,))
        row = cursor.fetchone()
        if row:
            names["project_name"] = row[0] or ""
            names["project_reference"] = row[1] or ""
            names["project_location"] = row[2] or ""
    return names


def _effective_amount(regime: str, hours, hourly_rate, agreed_amount) -> Decimal:
    if regime == "aangenomen werk":
        return _money(agreed_amount)
    return _money(_decimal(hours) * _decimal(hourly_rate))


def create_invoice_input(data: dict) -> tuple[int, int]:
    year = int(data.get("year") or date.today().year)
    week_number = int(data.get("week_number") or date.today().isocalendar().week)
    run_id = int(data["run_id"]) if data.get("run_id") else create_invoice_run(year, week_number, data.get("invoice_date"))
    regime = str(data.get("regime") or "regie").strip().lower()
    regime = "aangenomen werk" if regime in {"aangenomen", "aangenomen werk"} else "regie"
    hours = _decimal(data.get("hours"))
    hourly_rate = Decimal("0")
    agreed_amount = _money(data.get("agreed_amount"))
    supplied_fee = str(data.get("fee_percent") or "").strip()
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            agreement = _agreement_row(cursor, data.get("agreement_id"))
            relation_id = data.get("relation_id")
            principal_id = data.get("principal_id")
            project_id = data.get("project_id")
            if agreement:
                if agreement["status"] != "getekend":
                    raise ValueError("Alleen een getekende overeenkomst kan worden gebruikt voor een weekkoppeling.")
                relation_id = agreement["relation_id"]
                principal_id = agreement["principal_id"]
                project_id = agreement["project_id"]
                regime = agreement["regime"]
            names = _lookup_names(cursor, relation_id, principal_id, project_id)
            hourly_rate = _money(agreement["hourly_rate"] if agreement and regime == "regie" else data.get("hourly_rate") or names.get("employee_hourly_rate"))
            labor_amount = _effective_amount(regime, hours, hourly_rate, agreed_amount)
            factoring = bool(data.get("factoring")) or names.get("employee_payment_method") == "factoring"
            sepa_active = bool(data.get("sepa_active")) or names.get("employee_payment_method") != "geen_incasso"
            services = str(data.get("services") or ("a,b,c" if factoring else "a,b,c,d"))
            if factoring and not supplied_fee and services == "a,b,c,d":
                services = "a,b,c"
            fee_percent = _money(supplied_fee or (FACTORING_FEE_PERCENT if factoring else DEFAULT_FEE_PERCENT))
            cursor.execute(
                """
                INSERT INTO invoice_inputs (
                    run_id, relation_id, principal_id, project_id, agreement_id,
                    employee_name, principal_name, project_name, project_reference, project_location,
                    regime, hours, hourly_rate, agreed_amount, labor_amount,
                    parking_costs, material_costs, other_sales_costs,
                    olympus_costs, olympus_cost_description,
                    sales_vat_rate, fee_percent, services,
                    sepa_active, factoring, factoring_company, factoring_iban,
                    factoring_address, factoring_city, factoring_email, factoring_phone, factoring_kvk,
                    supplier_invoice_number, supplier_invoice_suffix, payment_term_days,
                    source_type, status, notes
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    'handmatig', 'concept', %s
                )
                RETURNING id;
                """,
                (
                    run_id, relation_id or None, principal_id or None, project_id or None, agreement["id"] if agreement else None,
                    names["employee_name"] or str(data.get("employee_name") or "").strip(),
                    names["principal_name"] or str(data.get("principal_name") or "").strip(),
                    names["project_name"] or str(data.get("project_name") or "").strip(),
                    names["project_reference"] or str(data.get("project_reference") or "").strip(),
                    names.get("project_location", "") or str(data.get("project_location") or "").strip(),
                    regime, hours, hourly_rate, agreed_amount, labor_amount,
                    _money(data.get("parking_costs")), _money(data.get("material_costs")), _money(data.get("other_sales_costs")),
                    _money(data.get("olympus_costs")), str(data.get("olympus_cost_description") or "Olympus-kosten").strip(),
                    _money(data.get("sales_vat_rate")), fee_percent, services,
                    sepa_active, factoring, str(data.get("factoring_company") or "Pronkert Factoring B.V.").strip(),
                    str(data.get("factoring_iban") or "").strip(), str(data.get("factoring_address") or "").strip(),
                    str(data.get("factoring_city") or "").strip(), str(data.get("factoring_email") or "").strip(),
                    str(data.get("factoring_phone") or "").strip(), str(data.get("factoring_kvk") or "").strip(),
                    str(data.get("supplier_invoice_number") or "").strip(), str(data.get("supplier_invoice_suffix") or "").strip(),
                    int(data.get("payment_term_days") or 30), str(data.get("notes") or "").strip(),
                ),
            )
            input_id = cursor.fetchone()[0]
        conn.commit()
    return run_id, input_id


def update_invoice_input(input_id: int, data: dict) -> int:
    regime = str(data.get("regime") or "regie").strip().lower()
    regime = "aangenomen werk" if regime in {"aangenomen", "aangenomen werk"} else "regie"
    hours = _decimal(data.get("hours"))
    hourly_rate = _money(data.get("hourly_rate"))
    agreed_amount = _money(data.get("agreed_amount"))
    labor_amount = _effective_amount(regime, hours, hourly_rate, agreed_amount)
    factoring = bool(data.get("factoring"))
    fee_percent = _money(data.get("fee_percent") or (FACTORING_FEE_PERCENT if factoring else DEFAULT_FEE_PERCENT))
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT project_id, project_name, project_reference, project_location
                FROM invoice_inputs
                WHERE id = %s;
                """,
                (input_id,),
            )
            existing = cursor.fetchone()
            if not existing:
                raise ValueError("Factuurregel niet gevonden.")

            project_id, project_name, project_reference, project_location = existing
            selected_project_id = str(data.get("project_id") or "").strip()
            if selected_project_id:
                cursor.execute(
                    """
                    SELECT id, title, COALESCE(reference_number, ''), COALESCE(location, '')
                    FROM vacancies
                    WHERE id = %s;
                    """,
                    (int(selected_project_id),),
                )
                project = cursor.fetchone()
                if not project:
                    raise ValueError("Project niet gevonden.")
                project_id, project_name, project_reference, project_location = project

            cursor.execute(
                """
                UPDATE invoice_inputs
                SET regime = %s, hours = %s, hourly_rate = %s, agreed_amount = %s, labor_amount = %s,
                    project_id = %s, project_name = %s, project_reference = %s, project_location = %s,
                    parking_costs = %s, material_costs = %s, other_sales_costs = %s,
                    olympus_costs = %s, olympus_cost_description = %s, sales_vat_rate = %s,
                    fee_percent = %s, services = %s, sepa_active = %s, factoring = %s,
                    factoring_company = %s, factoring_iban = %s, factoring_address = %s, factoring_city = %s,
                    factoring_email = %s, factoring_phone = %s, factoring_kvk = %s,
                    supplier_invoice_number = %s, supplier_invoice_suffix = %s,
                    payment_term_days = %s, notes = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING run_id;
                """,
                (
                    regime, hours, hourly_rate, agreed_amount, labor_amount,
                    project_id, project_name, project_reference, project_location,
                    _money(data.get("parking_costs")), _money(data.get("material_costs")), _money(data.get("other_sales_costs")),
                    _money(data.get("olympus_costs")), str(data.get("olympus_cost_description") or "Olympus-kosten").strip(),
                    _money(data.get("sales_vat_rate")), fee_percent, str(data.get("services") or ("a,b,c" if factoring else "a,b,c,d")),
                    bool(data.get("sepa_active")), factoring, str(data.get("factoring_company") or "Pronkert Factoring B.V.").strip(),
                    str(data.get("factoring_iban") or "").strip(), str(data.get("factoring_address") or "").strip(),
                    str(data.get("factoring_city") or "").strip(), str(data.get("factoring_email") or "").strip(),
                    str(data.get("factoring_phone") or "").strip(), str(data.get("factoring_kvk") or "").strip(),
                    str(data.get("supplier_invoice_number") or "").strip(), str(data.get("supplier_invoice_suffix") or "").strip(),
                    int(data.get("payment_term_days") or 30), str(data.get("notes") or "").strip(), input_id,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Factuurregel niet gevonden.")
            run_id = row[0]
        conn.commit()
    return run_id


def import_project_bookings_into_run(run_id: int) -> int:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            run = _run_row(cursor, run_id)
            if not run:
                raise ValueError("Factuurrun niet gevonden.")
            _, year, week_number, _, status, _, _ = run
            if status != "concept":
                raise ValueError("Een definitieve factuurrun kan niet meer worden aangevuld.")
            cursor.execute(
                """
                SELECT b.relation_id, b.principal_id, b.project_id,
                       COALESCE(r.name, w.employee_name, w.matched_candidate_name, '') AS employee_name,
                       COALESCE(p.name, w.principal_name, '') AS principal_name,
                       COALESCE(v.title, w.project_name, '') AS project_name,
                       COALESCE(v.reference_number, '') AS project_reference,
                       COALESCE(v.location, '') AS project_location,
                       COALESCE(SUM(b.hours), 0) AS hours
                FROM project_time_bookings b
                LEFT JOIN relations r ON r.id = b.relation_id
                LEFT JOIN relations p ON p.id = b.principal_id
                LEFT JOIN vacancies v ON v.id = b.project_id
                LEFT JOIN whatsapp_timesheet_inbox w ON w.id = b.timesheet_inbox_id
                WHERE EXTRACT(ISOYEAR FROM b.work_date) = %s
                  AND EXTRACT(WEEK FROM b.work_date) = %s
                  AND COALESCE(b.status, '') NOT IN ('verwijderd', 'deleted')
                GROUP BY b.relation_id, b.principal_id, b.project_id,
                         r.name, w.employee_name, w.matched_candidate_name,
                         p.name, w.principal_name, v.title, w.project_name,
                         v.reference_number, v.location
                ORDER BY employee_name, principal_name, project_name;
                """,
                (year, week_number),
            )
            source_rows = cursor.fetchall()
            inserted = 0
            for row in source_rows:
                relation_id, principal_id, project_id = row[:3]
                cursor.execute(
                    """
                    SELECT id FROM invoice_inputs
                    WHERE run_id = %s
                      AND relation_id IS NOT DISTINCT FROM %s
                      AND principal_id IS NOT DISTINCT FROM %s
                      AND project_id IS NOT DISTINCT FROM %s;
                    """,
                    (run_id, relation_id, principal_id, project_id),
                )
                if cursor.fetchone():
                    continue
                cursor.execute(
                    """
                    INSERT INTO invoice_inputs (
                        run_id, relation_id, principal_id, project_id,
                        employee_name, principal_name, project_name, project_reference, project_location,
                        regime, hours, hourly_rate, agreed_amount, labor_amount,
                        sales_vat_rate, fee_percent, services, sepa_active, factoring,
                        source_type, status, notes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'regie', %s, 0, 0, 0, 0, %s, 'a,b,c,d', TRUE, FALSE,
                            'gevalideerde uren', 'concept', 'Tarief en factuurgegevens nog valideren.')
                    RETURNING id;
                    """,
                    (run_id, relation_id, principal_id, project_id, row[3], row[4], row[5], row[6], row[7], row[8], DEFAULT_FEE_PERCENT),
                )
                cursor.fetchone()
                inserted += 1
        conn.commit()
    return inserted


def _input_row(cursor, input_id: int):
    cursor.execute(
        """
        SELECT i.id, i.run_id, i.relation_id, i.principal_id, i.project_id, i.agreement_id,
               i.employee_name, i.principal_name, i.project_name, i.project_reference, i.project_location,
               i.regime, i.hours, i.hourly_rate, i.agreed_amount, i.labor_amount,
               i.parking_costs, i.material_costs, i.other_sales_costs,
               i.olympus_costs, i.olympus_cost_description,
               i.sales_vat_rate, i.fee_percent, i.services, i.sepa_active, i.factoring,
               i.factoring_company, i.factoring_iban, i.factoring_address, i.factoring_city,
               i.factoring_email, i.factoring_phone, i.factoring_kvk,
               i.supplier_invoice_number, i.supplier_invoice_suffix, i.payment_term_days,
               i.source_type, i.status, i.notes
        FROM invoice_inputs i
        WHERE i.id = %s;
        """,
        (input_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    keys = (
        "id", "run_id", "relation_id", "principal_id", "project_id", "agreement_id", "employee_name", "principal_name", "project_name",
        "project_reference", "project_location", "regime", "hours", "hourly_rate", "agreed_amount", "labor_amount",
        "parking_costs", "material_costs", "other_sales_costs", "olympus_costs", "olympus_cost_description",
        "sales_vat_rate", "fee_percent", "services", "sepa_active", "factoring", "factoring_company", "factoring_iban",
        "factoring_address", "factoring_city", "factoring_email", "factoring_phone", "factoring_kvk", "supplier_invoice_number",
        "supplier_invoice_suffix", "payment_term_days", "source_type", "status", "notes",
    )
    item = dict(zip(keys, row))
    item.update({
        "employee": {},
        "principal": {},
    })
    for target, relation_id in (("employee", item.get("relation_id")), ("principal", item.get("principal_id"))):
        if relation_id:
            cursor.execute(
                """
                SELECT name, first_name, last_name, contact_name, email, phone, street,
                       house_number, house_number_addition, postal_code, city, country,
                       kvk_number, vat_number, COALESCE(logo_path, photo_path, ''),
                       COALESCE(invoice_obs_number, ''), COALESCE(invoice_payment_method, ''),
                       COALESCE(invoice_customer_number, '')
                FROM relations WHERE id = %s;
                """,
                (relation_id,),
            )
            relation = cursor.fetchone()
            if relation:
                item[target] = dict(zip((
                    "name", "first_name", "last_name", "contact_name", "email", "phone", "street",
                    "house_number", "house_number_addition", "postal_code", "city", "country", "kvk_number",
                    "vat_number", "logo_path", "invoice_obs_number", "invoice_payment_method",
                    "invoice_customer_number",
                ), relation))
    for key in ("hours", "hourly_rate", "agreed_amount", "labor_amount", "parking_costs", "material_costs", "other_sales_costs", "olympus_costs", "sales_vat_rate", "fee_percent"):
        item[f"{key}_text"] = _number_text(item[key])
    item["sales_costs"] = _money(item["parking_costs"]) + _money(item["material_costs"]) + _money(item["other_sales_costs"])
    item["sales_total"] = _money(item["labor_amount"]) + item["sales_costs"]
    item["fee_amount"] = _money(_money(item["labor_amount"]) * _decimal(item["fee_percent"]) / Decimal("100"))
    item["admin_fee"] = Decimal("0") if item["sepa_active"] else DEFAULT_ADMIN_FEE
    item["olympus_vat"] = _money((item["fee_amount"] + item["admin_fee"]) * OLYMPUS_VAT_RATE / Decimal("100"))
    item["olympus_total"] = item["fee_amount"] + item["admin_fee"] + item["olympus_vat"] + _money(item["olympus_costs"])
    item["sales_vat"] = _money(item["sales_total"] * _decimal(item["sales_vat_rate"]) / Decimal("100"))
    item["sales_total_including_vat"] = item["sales_total"] + item["sales_vat"]
    item["sales_total_including_vat_text"] = _money_text(item["sales_total_including_vat"])
    item["olympus_total_text"] = _money_text(item["olympus_total"])
    item["blockers"] = _input_blockers(item)
    item["display_status"] = "Klaar voor concept" if not item["blockers"] else "Aanvullen"
    return item


def _safe_document_path(path_value: str | Path) -> Path | None:
    path = Path(path_value).resolve()
    for root in (INVOICE_DOCUMENT_DIR.resolve(), INVOICE_EXPORT_DIR.resolve()):
        try:
            path.relative_to(root)
            return path if path.is_file() else None
        except ValueError:
            continue
    return None


def get_invoice_document_path(document_id: int) -> Path | None:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_path FROM invoice_documents WHERE id = %s;", (document_id,))
            row = cursor.fetchone()
    return _safe_document_path(row[0]) if row else None


def _remove_managed_file(path_value: str | Path) -> None:
    path = Path(path_value).resolve()
    for root in (INVOICE_DOCUMENT_DIR.resolve(), INVOICE_EXPORT_DIR.resolve()):
        try:
            path.relative_to(root)
        except ValueError:
            continue
        if path.is_file():
            path.unlink()
        return


def delete_invoice_output(output_id: int) -> int:
    _ensure()
    paths = []
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_path FROM invoice_outputs WHERE id = %s;", (output_id,))
            output = cursor.fetchone()
            if not output:
                raise ValueError("Factuur niet gevonden.")
            paths.append(output[0])
            cursor.execute("SELECT file_path FROM invoice_documents WHERE output_id = %s;", (output_id,))
            paths.extend(row[0] for row in cursor.fetchall())
            cursor.execute("DELETE FROM invoice_documents WHERE output_id = %s;", (output_id,))
            cursor.execute("DELETE FROM invoice_outputs WHERE id = %s;", (output_id,))
        conn.commit()
    for path in set(paths):
        _remove_managed_file(path)
    return output_id


def delete_invoice_document(document_id: int) -> int:
    _ensure()
    output_id = None
    path = ""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT output_id, file_path FROM invoice_documents WHERE id = %s;", (document_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Document niet gevonden.")
            output_id, path = row
            if not output_id:
                cursor.execute("DELETE FROM invoice_documents WHERE id = %s;", (document_id,))
        if not output_id:
            conn.commit()
    if output_id:
        return delete_invoice_output(output_id)
    _remove_managed_file(path)
    return document_id


def delete_invoice_run(run_id: int) -> dict:
    _ensure()
    paths = []
    with get_connection() as conn:
        with conn.cursor() as cursor:
            run = _run_row(cursor, run_id)
            if not run:
                raise ValueError("Factuurrun niet gevonden.")
            cursor.execute(
                """
                SELECT DISTINCT file_path FROM invoice_documents
                WHERE run_id = %s
                   OR input_id IN (SELECT id FROM invoice_inputs WHERE run_id = %s)
                   OR output_id IN (SELECT id FROM invoice_outputs WHERE run_id = %s);
                """,
                (run_id, run_id, run_id),
            )
            paths.extend(row[0] for row in cursor.fetchall())
            cursor.execute("SELECT file_path FROM invoice_outputs WHERE run_id = %s;", (run_id,))
            paths.extend(row[0] for row in cursor.fetchall())
            cursor.execute(
                """
                DELETE FROM invoice_documents
                WHERE run_id = %s
                   OR input_id IN (SELECT id FROM invoice_inputs WHERE run_id = %s)
                   OR output_id IN (SELECT id FROM invoice_outputs WHERE run_id = %s);
                """,
                (run_id, run_id, run_id),
            )
            cursor.execute("DELETE FROM invoice_runs WHERE id = %s;", (run_id,))
        conn.commit()
    for path in set(paths):
        _remove_managed_file(path)
    return {"run_id": run_id, "file_count": len(set(paths))}


def save_invoice_document(content: bytes, filename: str, document_type: str, relation_id=None, principal_id=None,
                          project_id=None, run_id=None, input_id=None, output_id=None, agreement_id=None) -> int:
    if not content or not filename:
        raise ValueError("Kies een document om te uploaden.")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx"}:
        raise ValueError("Dit bestandstype wordt niet ondersteund.")
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            employee_name = "onbekende_zzper"
            if relation_id:
                cursor.execute("SELECT name FROM relations WHERE id = %s;", (relation_id,))
                relation = cursor.fetchone()
                employee_name = relation[0] if relation else employee_name
            dossier_dir = INVOICE_DOCUMENT_DIR / _dossier_name(employee_name)
            dossier_dir.mkdir(parents=True, exist_ok=True)
            safe_filename = f"{uuid4().hex}_{Path(filename).name}"
            path = dossier_dir / safe_filename
            path.write_bytes(content)
            cursor.execute(
                """
                INSERT INTO invoice_documents
                    (relation_id, principal_id, project_id, run_id, input_id, output_id, agreement_id,
                     document_type, filename, file_path, content_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (relation_id or None, principal_id or None, project_id or None, run_id or None, input_id or None,
                 output_id or None, agreement_id or None, str(document_type or "overig"), Path(filename).name, str(path),
                 guess_type(filename)[0] or "application/octet-stream"),
            )
            document_id = cursor.fetchone()[0]
        conn.commit()
    return document_id


def list_invoice_documents(query: str = "", relation_id: int | None = None) -> list[dict]:
    _ensure()
    search = f"%{str(query or '').strip().lower()}%"
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT d.id, d.relation_id, d.principal_id, d.project_id, d.run_id, d.input_id,
                       d.output_id, d.document_type, d.filename, d.content_type, d.created_at,
                       COALESCE(r.name, i.employee_name, '') AS employee_name,
                       COALESCE(p.name, i.principal_name, '') AS principal_name,
                       COALESCE(v.title, i.project_name, '') AS project_name
                FROM invoice_documents d
                LEFT JOIN relations r ON r.id = d.relation_id
                LEFT JOIN relations p ON p.id = d.principal_id
                LEFT JOIN invoice_inputs i ON i.id = d.input_id
                LEFT JOIN vacancies v ON v.id = d.project_id
                WHERE (%s = '%%' OR LOWER(CONCAT_WS(' ', d.filename, d.document_type, r.name, p.name,
                       i.employee_name, i.principal_name, v.title, d.run_id::text)) LIKE %s)
                  AND (%s IS NULL OR d.relation_id = %s)
                ORDER BY d.created_at DESC, d.id DESC
                LIMIT 200;
                """,
                (search, search, relation_id, relation_id),
            )
            rows = cursor.fetchall()
    return [dict(zip(("id", "relation_id", "principal_id", "project_id", "run_id", "input_id", "output_id",
                      "document_type", "filename", "content_type", "created_at", "employee_name", "principal_name", "project_name"), row)) for row in rows]


def list_relation_invoice_documents(relation_id: int) -> list[dict]:
    return list_invoice_documents(relation_id=relation_id)


def _input_blockers(item: dict) -> list[str]:
    blockers = []
    for key, label in (("employee_name", "zzp'er"), ("principal_name", "opdrachtgever"), ("project_name", "project")):
        if not str(item.get(key) or "").strip():
            blockers.append(f"{label.capitalize()} ontbreekt")
    if item.get("regime") == "regie" and (_decimal(item.get("hours")) <= 0 or _decimal(item.get("hourly_rate")) <= 0):
        blockers.append("Uren en regietarief invullen")
    if item.get("regime") == "aangenomen werk" and _decimal(item.get("agreed_amount")) <= 0:
        blockers.append("Aanneemsom invullen")
    if not str(item.get("supplier_invoice_number") or "").strip():
        blockers.append("Factuurnummer zzp'er ontbreekt")
    if _decimal(item.get("sales_vat_rate")) not in {Decimal("0"), Decimal("21")}:
        blockers.append("Kies verlegd of 21% btw")
    return blockers


def get_invoice_output_path(output_id: int) -> Path | None:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_path FROM invoice_outputs WHERE id = %s;", (output_id,))
            row = cursor.fetchone()
    if not row:
        return None
    path = Path(row[0]).resolve()
    root = INVOICE_EXPORT_DIR.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path if path.is_file() else None


def _output_number(cursor, run_id: int, input_id: int, stream: str) -> str | None:
    cursor.execute("SELECT invoice_number FROM invoice_outputs WHERE run_id = %s AND input_id = %s AND stream = %s;", (run_id, input_id, stream))
    row = cursor.fetchone()
    return row[0] if row else None


def _next_olympus_number(cursor) -> str:
    cursor.execute("SELECT next_number FROM invoice_number_sequences WHERE sequence_key = 'olympus';")
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO invoice_number_sequences (sequence_key, next_number) VALUES ('olympus', 50083) RETURNING next_number;")
        number = int(cursor.fetchone()[0])
    else:
        number = int(row[0])
    cursor.execute("UPDATE invoice_number_sequences SET next_number = %s, updated_at = NOW() WHERE sequence_key = 'olympus';", (number + 1,))
    return str(number)


def _supplier_invoice_number(item: dict) -> str:
    number = str(item.get("supplier_invoice_number") or "").strip()
    suffix = str(item.get("supplier_invoice_suffix") or "").strip()
    if number:
        return f"{number}-{suffix}" if suffix else number
    return f"ZZP-{item.get('relation_id') or 'onbekend'}-{item['id']}"


def _dossier_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9À-ÿ]+", "_", str(value or "onbekende_zzper").strip()).strip("_")
    return cleaned or "onbekende_zzper"


def _document_filename_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(". ")
    return cleaned or fallback


def _output_filename(stream: str, item: dict, run: dict, invoice_number: str) -> str:
    employee_name = _document_filename_part(item.get("employee_name"), "Onbekende zzp'er")
    safe_number = _document_filename_part(invoice_number, "concept")
    week_label = f"week {run['week_number']} {run['year']}"
    if stream == "verkoop":
        number_label = safe_number if re.search(r"\bOBS\b", safe_number, flags=re.IGNORECASE) else f"{safe_number} OBS"
        return f"Factuur {number_label} - {employee_name} {week_label}.pdf"
    return f"Olympus-factuur {safe_number} - {employee_name} {week_label}.pdf"


def _services_text(item: dict) -> str:
    services = [part.strip().lower() for part in str(item.get("services") or "").split(",") if part.strip()]
    return f"3.1 {', '.join(services)}" if services and services != ["a", "b", "c", "d"] else "optionele diensten art. 3.1"


def _relation_full_name(relation: dict, fallback: str) -> str:
    name = " ".join(str(relation.get(key) or "").strip() for key in ("first_name", "last_name")).strip()
    return name or str(relation.get("name") or fallback or "").strip()


def _relation_address_lines(relation: dict) -> list[str]:
    street = " ".join(str(relation.get(key) or "").strip() for key in ("street", "house_number", "house_number_addition")).strip()
    city = " ".join(str(relation.get(key) or "").strip() for key in ("postal_code", "city")).strip()
    return [line for line in (street, city) if line]


def _draw_lines(c, x: float, y: float, lines: list[str], color="#111111", font="Helvetica", size=9, leading=12):
    colors, _, _ = _reportlab_dependencies()
    c.setFillColor(colors.HexColor(color))
    c.setFont(font, size)
    for line in lines:
        if line:
            c.drawString(x, y, str(line))
            y -= leading
    return y


def _draw_logo(c, logo_path: str | None, x: float, y: float, max_width: float = 120, max_height: float = 62) -> None:
    if not logo_path or not Path(logo_path).is_file():
        return
    try:
        from reportlab.lib.utils import ImageReader
        image = ImageReader(logo_path)
        image_width, image_height = image.getSize()
        scale = min(max_width / image_width, max_height / image_height)
        c.drawImage(image, x, y - image_height * scale, image_width * scale, image_height * scale, mask="auto", preserveAspectRatio=True)
    except Exception as exc:
        print(f"INVOICE_LOGO_WARNING {type(exc).__name__}: {exc}")


def _brand_logo_path(cursor) -> str | None:
    cursor.execute("SELECT file_path FROM invoice_brand_assets WHERE asset_key = 'olympus_logo';")
    row = cursor.fetchone()
    if row and Path(row[0]).is_file():
        return row[0]
    default_logo = Path("apps/dashboard/static/olympusbouw.png")
    return str(default_logo) if default_logo.is_file() else None


def _merge_pdf_documents(output_path: Path, invoice_path: Path, attachment_paths: list[Path]) -> None:
    pdf_attachments = [path for path in attachment_paths if path.suffix.lower() == ".pdf" and path.is_file()]
    if not pdf_attachments:
        invoice_path.replace(output_path)
        return
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.append(str(invoice_path))
    for attachment_path in pdf_attachments:
        writer.append(str(attachment_path))
    with output_path.open("wb") as handle:
        writer.write(handle)
    invoice_path.unlink(missing_ok=True)


def _input_attachment_paths(cursor, input_id: int) -> list[Path]:
    cursor.execute(
        """
        SELECT file_path FROM invoice_documents
        WHERE input_id = %s AND output_id IS NULL
        ORDER BY CASE document_type
            WHEN 'weekstaat' THEN 1
            WHEN 'parkeerdeclaratie' THEN 2
            WHEN 'materiaaldeclaratie' THEN 3
            WHEN 'overige_bijlage' THEN 4
            WHEN 'overeenkomst' THEN 5
            ELSE 6 END, id;
        """,
        (input_id,),
    )
    return [Path(row[0]) for row in cursor.fetchall() if _safe_document_path(row[0])]


def _factuur_kader(c, x: float, y: float, width: float, height: float, rows: list[tuple[str, str, str, str]], accent="#111111") -> None:
    colors, _, _ = _reportlab_dependencies()
    c.setStrokeColor(colors.HexColor(accent))
    c.setLineWidth(0.65)
    c.rect(x, y, width, height, fill=0, stroke=1)
    c.line(x + width * 0.52, y, x + width * 0.52, y + height)
    row_height = height / len(rows)
    for index, (left_label, left_value, right_label, right_value) in enumerate(rows):
        if index:
            c.line(x, y + height - row_height * index, x + width, y + height - row_height * index)
        baseline = y + height - row_height * index - row_height * 0.67
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x + 8, baseline, left_label)
        c.setFont("Helvetica", 8)
        c.drawString(x + 62, baseline, str(left_value or "-"))
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(x + width * 0.52 + 8, baseline, right_label)
        c.setFont("Helvetica", 8)
        c.drawString(x + width * 0.52 + 62, baseline, str(right_value or "-"))


def _agreement_pdf_context(data: dict) -> dict:
    relation_id = int(data.get("relation_id") or 0)
    principal_id = int(data.get("principal_id") or 0)
    project_id = int(data.get("project_id") or 0)
    if not all((relation_id, principal_id, project_id)):
        raise ValueError("Kies een zzp'er, opdrachtgever en project voor de PDF-preview.")
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            names = _lookup_names(cursor, relation_id, principal_id, project_id)
            cursor.execute(
                """
                SELECT name, first_name, last_name, contact_name, email, phone, street, house_number,
                       house_number_addition, postal_code, city, kvk_number, vat_number,
                       COALESCE(logo_path, photo_path, ''), COALESCE(invoice_obs_number, '')
                FROM relations WHERE id = %s;
                """,
                (relation_id,),
            )
            employee_row = cursor.fetchone()
            cursor.execute(
                """
                SELECT name, contact_name, email, street, house_number, house_number_addition,
                       postal_code, city, kvk_number, vat_number, COALESCE(invoice_customer_number, '')
                FROM relations WHERE id = %s;
                """,
                (principal_id,),
            )
            principal_row = cursor.fetchone()
    employee = dict(zip((
        "name", "first_name", "last_name", "contact_name", "email", "phone", "street", "house_number",
        "house_number_addition", "postal_code", "city", "kvk_number", "vat_number", "logo_path", "obs_number",
    ), employee_row or ("",) * 15))
    principal = dict(zip((
        "name", "contact_name", "email", "street", "house_number", "house_number_addition", "postal_code",
        "city", "kvk_number", "vat_number", "customer_number",
    ), principal_row or ("",) * 11))
    regime = "aangenomen werk" if str(data.get("regime") or "").strip().lower() in {"aangenomen", "aangenomen werk"} else "regie"
    return {
        "relation_id": relation_id,
        "principal_id": principal_id,
        "project_id": project_id,
        "employee": employee,
        "principal": principal,
        "employee_name": names["employee_name"],
        "principal_name": names["principal_name"],
        "project_name": names["project_name"],
        "project_reference": names["project_reference"],
        "project_location": names["project_location"],
        "regime": regime,
        "hourly_rate": _money(data.get("hourly_rate")),
        "start_date": _parse_date(data.get("start_date")),
        "end_date": str(data.get("end_date") or "").strip(),
        "status": str(data.get("status") or "concept").strip(),
        "notes": str(data.get("notes") or "").strip(),
    }


def _agreement_pdf_bytes(data: dict) -> bytes:
    context = _agreement_pdf_context(data)
    colors, A4, canvas = _reportlab_dependencies()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    employee = context["employee"]
    principal = context["principal"]
    employee_name = _relation_full_name(employee, context["employee_name"])
    principal_name = principal.get("name") or context["principal_name"]
    obs_code = f"ZZP OBS {employee.get('obs_number') or context['relation_id']} {principal.get('customer_number') or context['principal_id']}"
    brand_logo = None
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            brand_logo = _brand_logo_path(cursor)

    _draw_logo(c, brand_logo, 410, height - 36, 120, 58)
    c.setFillColor(colors.HexColor("#24559c"))
    c.setFont("Helvetica-Bold", 21)
    c.drawString(42, height - 65, "OPDRACHTFORMULIER")
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    c.drawString(42, height - 84, "Uitvoeringsovereenkomst voor zzp-opdracht in de bouw")
    _draw_lines(c, 42, height - 124, ["Opdrachtgever", principal_name, f"T.a.v. {principal.get('contact_name') or 'Financiele administratie'}"] + _relation_address_lines(principal), size=9, leading=12)
    _draw_lines(c, 302, height - 124, ["Opdrachtnemer", employee_name, employee.get("name") or employee_name] + _relation_address_lines(employee), size=9, leading=12)
    _factuur_kader(c, 42, height - 300, width - 84, 84, [
        ("OBS-code", obs_code, "Project", context["project_name"]),
        ("Ingangsdatum", _date_text(context["start_date"]), "Werknummer", context["project_reference"] or "-"),
        ("Regime", "Regie" if context["regime"] == "regie" else "Aangenomen werk", "Plaats", context["project_location"] or "-"),
        ("Tarief", _money_text(context["hourly_rate"]) + " per uur" if context["regime"] == "regie" else "Volgens aanneemsom per week", "Status", context["status"].capitalize()),
    ], accent="#24559c")
    y = height - 340
    c.setFillColor(colors.HexColor("#111111"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(42, y, "Afspraken over de opdracht")
    c.setFont("Helvetica", 9)
    lines = [
        f"{employee_name} voert werkzaamheden uit voor {principal_name} op bovengenoemd project.",
        "De werkzaamheden worden zelfstandig uitgevoerd; Olympus Bouw B.V. bemiddelt en verzorgt de facturatie.",
        f"Facturatie vindt plaats op basis van de geaccordeerde weekstaat onder referentie {obs_code}.",
        "Doorbelaste parkeer- en materiaalkosten worden uitsluitend met bijbehorende bewijsstukken verwerkt.",
    ]
    for line in lines:
        c.drawString(48, y - 18, line)
        y -= 18
    if context["notes"]:
        c.setFont("Helvetica-Oblique", 8.5)
        c.drawString(48, y - 10, f"Bijzonderheden: {context['notes']}")
        y -= 24
    c.setStrokeColor(colors.HexColor("#24559c"))
    c.line(42, 150, 250, 150)
    c.line(330, 150, 538, 150)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 137, "Opdrachtgever: naam, datum en handtekening")
    c.drawString(330, 137, "Opdrachtnemer: naam, datum en handtekening")
    c.setFillColor(colors.HexColor("#6b777d"))
    c.drawString(42, 36, "Olympus Bouw B.V. | Bemiddeling en facturatie namens de zelfstandige")
    c.showPage()

    _draw_logo(c, brand_logo, 410, height - 36, 120, 58)
    c.setFillColor(colors.HexColor("#24559c"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(42, height - 65, "MODELOVEREENKOMST")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(42, height - 88, "Aanneming van werk")
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    article_lines = [
        ("1. Partijen", f"Opdrachtgever {principal_name} en opdrachtnemer {employee_name} sluiten deze uitvoeringsovereenkomst."),
        ("2. Opdracht", f"De opdracht betreft {context['project_name']} ({context['project_reference'] or 'werknummer volgt'}) te {context['project_location'] or 'nader te bepalen plaats'}."),
        ("3. Uitvoering", "De opdrachtnemer bepaalt zelfstandig de wijze van uitvoering, planning en inzet binnen de overeengekomen opdracht."),
        ("4. Vergoeding", _money_text(context["hourly_rate"]) + " per uur exclusief btw en exclusief doorbelastbare kosten." if context["regime"] == "regie" else "De vergoeding wordt per geaccordeerde aanneemsom en weekstaat vastgesteld."),
        ("5. Facturatie", f"Olympus Bouw B.V. verzorgt de facturatie namens de opdrachtnemer met OBS-code {obs_code}."),
        ("6. Geldigheid", f"Deze overeenkomst gaat in op {_date_text(context['start_date'])}" + (f" en eindigt op {context['end_date']}." if context["end_date"] else ".")),
    ]
    y = height - 130
    for title, text in article_lines:
        c.setFillColor(colors.HexColor("#24559c"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(42, y, title)
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica", 9)
        y = _draw_lines(c, 48, y - 14, [text], size=9, leading=13) - 10
    c.setStrokeColor(colors.HexColor("#24559c"))
    c.line(42, 150, 250, 150)
    c.line(330, 150, 538, 150)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 137, "Namens opdrachtgever")
    c.drawString(330, 137, "Namens opdrachtnemer")
    c.drawString(42, 36, f"Referentie: {obs_code} | Gegenereerd als conceptdocument")
    c.save()
    return buffer.getvalue()


def save_invoice_agreement_pdf(agreement_id: int) -> int:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            agreement = _agreement_row(cursor, agreement_id)
            if not agreement:
                raise ValueError("Overeenkomst niet gevonden.")
    content = _agreement_pdf_bytes(agreement)
    context = _agreement_pdf_context(agreement)
    filename = "Overeenkomst " + _document_filename_part(context["employee_name"], "zzper") + " - " + _document_filename_part(context["principal_name"], "opdrachtgever") + ".pdf"
    dossier_dir = INVOICE_EXPORT_DIR / _dossier_name(context["employee_name"])
    dossier_dir.mkdir(parents=True, exist_ok=True)
    path = dossier_dir / filename
    path.write_bytes(content)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM invoice_documents WHERE agreement_id = %s AND document_type = 'opdrachtovereenkomst';", (agreement_id,))
            cursor.execute(
                """
                INSERT INTO invoice_documents
                    (relation_id, principal_id, project_id, agreement_id, document_type, filename, file_path, content_type)
                VALUES (%s, %s, %s, %s, 'opdrachtovereenkomst', %s, %s, 'application/pdf')
                RETURNING id;
                """,
                (context["relation_id"], context["principal_id"], context["project_id"], agreement_id, filename, str(path)),
            )
            document_id = cursor.fetchone()[0]
        conn.commit()
    return document_id


def get_invoice_agreement_pdf_path(agreement_id: int) -> Path | None:
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT file_path FROM invoice_documents
                WHERE agreement_id = %s AND document_type = 'opdrachtovereenkomst'
                ORDER BY id DESC LIMIT 1;
                """,
                (agreement_id,),
            )
            row = cursor.fetchone()
    return _safe_document_path(row[0]) if row else None


def _amount_line(c, y: float, label: str, amount: str, detail: str = "", color="#111111") -> float:
    colors, _, _ = _reportlab_dependencies()
    c.setFillColor(colors.HexColor(color))
    c.setFont("Helvetica", 9)
    c.drawString(48, y, label)
    if detail:
        c.setFont("Helvetica", 7.5)
        c.drawString(48, y - 11, detail)
    c.setFont("Helvetica", 9)
    c.drawRightString(548, y, amount)
    return y - (25 if detail else 17)


def _sale_pdf(path: Path, run: dict, item: dict, invoice_number: str) -> None:
    colors, A4, canvas = _reportlab_dependencies()
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    employee = item.get("employee") or {}
    principal = item.get("principal") or {}
    principal_name = principal.get("name") or item["principal_name"]
    employee_name = _relation_full_name(employee, item["employee_name"])
    left_lines = [principal_name, f"T.a.v. {principal.get('contact_name') or 'De financiële administratie'}"] + _relation_address_lines(principal)
    if principal.get("email"):
        left_lines.append(f"Per e-mail: {principal['email']}")
    _draw_lines(c, 42, height - 52, left_lines, size=9, leading=12)
    _draw_logo(c, employee.get("logo_path"), 405, height - 35, 105, 55)
    right_lines = [employee_name] + _relation_address_lines(employee)
    if employee.get("kvk_number"):
        right_lines.append(f"KvK {employee['kvk_number']}")
    if employee.get("vat_number"):
        right_lines.append(f"BTW {employee['vat_number']}")
    if employee.get("phone"):
        right_lines.append(employee["phone"])
    if employee.get("email"):
        right_lines.append(employee["email"])
    _draw_lines(c, 405, height - 108, right_lines, size=8.5, leading=11)
    c.setFillColor(colors.HexColor("#111111"))
    c.setFont("Helvetica-Bold", 25)
    c.drawString(42, height - 225, "FACTUUR")
    _factuur_kader(c, 42, height - 310, width - 84, 68, [
        ("Factuur", invoice_number, "Project", item["project_name"]),
        ("Datum", _date_text(run["invoice_date"]), "Nummer", f"Werk: {item['project_reference'] or '-'}"),
        ("Plaats", employee.get("city") or "-", "Bon", "Factureren met weekstaat"),
        ("Week", f"{run['week_number']} {run['year']}", "BTW nr", principal.get("vat_number") or "-"),
    ])
    y = height - 345
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#111111"))
    c.drawString(48, y, "Betreft voor uw bedrijf uitgevoerde werkzaamheden conform overeenkomst")
    y -= 17
    obs_code = f"ZZP OBS {employee.get('invoice_obs_number') or item.get('relation_id') or '-'} {principal.get('invoice_customer_number') or item.get('principal_id') or '-'}"
    c.setFont("Helvetica", 8)
    c.drawString(48, y, obs_code)
    c.drawRightString(548, y, _money_text(item["labor_amount"]))
    y -= 28
    y = _amount_line(c, y, "Doorbelaste parkeerkosten", _money_text(item["parking_costs"]), "")
    y = _amount_line(c, y, "Doorbelaste materiaalkosten", _money_text(item["material_costs"]), "")
    if _money(item["other_sales_costs"]):
        y = _amount_line(c, y, "Overige doorbelaste kosten", _money_text(item["other_sales_costs"]), "")
    c.setStrokeColor(colors.black)
    c.line(42, y + 5, 550, y + 5)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(48, y - 10, "Totaal door u te voldoen")
    c.drawRightString(548, y - 10, _money_text(item["sales_total_including_vat"]))
    y -= 37
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    if _decimal(item["sales_vat_rate"]) == 0:
        c.drawString(48, y, "De BTW verleggingsregeling is van toepassing")
    else:
        c.drawString(48, y, f"BTW 21%: {_money_text(item['sales_vat'])} over {_money_text(item['sales_total'])}")
    y -= 32
    payment_date = run["invoice_date"] + timedelta(days=int(item["payment_term_days"] or 30))
    if item["factoring"]:
        c.setFillColor(colors.HexColor("#4d9b67"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(48, y, "Betaling van deze vordering dient plaats te vinden voor:")
        y -= 15
        c.drawString(48, y, _date_text(payment_date))
        y -= 17
        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica", 9)
        c.drawString(48, y, f"Op rekening {item['factoring_iban'] or '-'} ten name van {item['factoring_company']}")
        y -= 15
        c.drawString(48, y, "onder vermelding van het factuurnummer")
        y -= 35
        c.setFillColor(colors.HexColor("#7b1e1e"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(48, y, "FACTORING")
        y -= 17
        c.setFont("Helvetica", 9)
        c.drawString(48, y, f"{employee_name} maakt gebruik van factoring")
        c.drawString(48, y - 14, f"Het eigendom van de hierbij gefactureerde vordering is overgedragen aan {item['factoring_company']}")
    else:
        c.drawString(48, y, f"Betaling van deze vordering dient plaats te vinden voor: {_date_text(payment_date)}")
    c.setFillColor(colors.HexColor("#6b777d"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 34, "Factuur opgesteld namens de zzp'er")
    c.save()


def _olympus_pdf(path: Path, run: dict, item: dict, invoice_number: str, sale_invoice_number: str) -> None:
    colors, A4, canvas = _reportlab_dependencies()
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    employee = item.get("employee") or {}
    _draw_lines(c, 42, height - 52, [f"De heer {employee.get('first_name') or item['employee_name']} {employee.get('last_name') or ''}".strip(), item["employee_name"]] + _relation_address_lines(employee), size=9, leading=12)
    _draw_logo(c, item.get("olympus_logo_path"), 405, height - 35, 112, 58)
    _draw_lines(c, 405, height - 108, ["Olympus Bouw B.V.", "Hoofdweg 244", "2908 LC Capelle aan den IJssel", "Telefoon 0888 - 111 222", "info@olympusbouw.nl", "Handelsregister 32146718", "BTW NL.8204.26.003.B.01", "IBAN NL33 RABO 0148 7700 10"], color="#24559c", size=8, leading=10)
    c.setFillColor(colors.HexColor("#24559c"))
    c.setFont("Helvetica-Bold", 25)
    c.drawString(42, height - 225, "FACTUUR")
    _factuur_kader(c, 42, height - 310, width - 84, 68, [
        ("Factuur", invoice_number, "Project", item["project_name"]),
        ("Datum", f"{run['invoice_date'].day}-{run['invoice_date'].month}-{run['invoice_date'].year}", "Debiteurnr", item.get("relation_id") or "-"),
        ("Plaats", "Capelle aan den IJssel", "BTW nr", employee.get("vat_number") or "-"),
        ("Week", f"{run['week_number']} {run['year']}", "Werk", item["project_reference"] or "-"),
    ], accent="#24559c")
    y = height - 345
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 10)
    c.drawString(48, y, "Hierbij brengen wij u in rekening de aan u geleverde optionele dienstverlening op basis")
    c.drawString(48, y - 15, "van onze goedgekeurde bemiddelingsovereenkomst.")
    y -= 54
    y = _amount_line(c, y, f"Door u is aan uw opdrachtgever reeds gefactureerd met factuurnummer {sale_invoice_number}", _money_text(item["sales_total_including_vat"]), f"op basis van de door u te realiseren opdracht op het bovenvermelde project in week {run['week_number']} {run['year']}")
    y = _amount_line(c, y, f"Aan u geleverde optionele diensten {_services_text(item)}", _money_text(item["fee_amount"]), "")
    y = _amount_line(c, y, "Berekend over de omzet onder aftrek van e.v.t. door u doorbelaste kosten:", _money_text(item["labor_amount"]), "")
    if item["admin_fee"]:
        y = _amount_line(c, y, "Administratievergoeding wegens geen SEPA-incasso", _money_text(item["admin_fee"]), "")
    if _money(item["olympus_costs"]):
        y = _amount_line(c, y, item["olympus_cost_description"] or "Door ons aan u doorbelaste kosten", _money_text(item["olympus_costs"]), "")
    y -= 8
    y = _amount_line(c, y, "Verschuldigde 21% BTW", _money_text(item["olympus_vat"]), "Over fee en administratievergoeding")
    c.setStrokeColor(colors.black)
    c.line(42, y + 5, 550, y + 5)
    c.setFillColor(colors.HexColor("#111111"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(48, y - 10, "Totaal te voldoen")
    c.drawRightString(548, y - 10, _money_text(item["olympus_total"]))
    y -= 48
    debit_days = 8 if item["factoring"] else 30
    debit_date = run["invoice_date"] + timedelta(days=debit_days)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#4d9b67"))
    c.drawString(48, y, f"Het totaalbedrag wordt afgeschreven op: {_date_text(debit_date)}")
    c.setFillColor(colors.HexColor("#111111"))
    c.drawString(48, y - 15, "van uw rekening: " + (employee.get("iban") or "NL67 ABNA 0846 7711 36"))
    c.setFillColor(colors.HexColor("#6b777d"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 34, "Olympus Bouw B.V. | Hoofdweg 244 | 2908 LC Capelle aan den IJssel")
    c.save()


def generate_invoice_run(run_id: int) -> dict:
    _ensure()
    INVOICE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            run_row = _run_row(cursor, run_id)
            if not run_row:
                raise ValueError("Factuurrun niet gevonden.")
            run = {"id": run_row[0], "year": run_row[1], "week_number": run_row[2], "invoice_date": run_row[3], "status": run_row[4]}
            cursor.execute("SELECT id FROM invoice_inputs WHERE run_id = %s ORDER BY id;", (run_id,))
            input_ids = [row[0] for row in cursor.fetchall()]
            if not input_ids:
                raise ValueError("Voeg eerst minimaal één invoerregel toe.")
            items = []
            for input_id in input_ids:
                item = _input_row(cursor, input_id)
                if item["blockers"]:
                    raise ValueError(f"Regel {input_id}: " + ", ".join(item["blockers"]))
                items.append(item)
            output_ids = []
            for item in items:
                item["olympus_logo_path"] = _brand_logo_path(cursor)
                sale_number = _output_number(cursor, run_id, item["id"], "verkoop") or _supplier_invoice_number(item)
                olympus_number = _output_number(cursor, run_id, item["id"], "olympus") or _next_olympus_number(cursor)
                dossier_dir = INVOICE_EXPORT_DIR / _dossier_name(item["employee_name"])
                dossier_dir.mkdir(parents=True, exist_ok=True)
                sale_path = dossier_dir / _output_filename("verkoop", item, run, sale_number)
                olympus_path = dossier_dir / _output_filename("olympus", item, run, olympus_number)
                sale_base = dossier_dir / f".verkoopfactuur_{run_id}_{item['id']}.pdf"
                olympus_base = dossier_dir / f".olympusfactuur_{run_id}_{item['id']}.pdf"
                _sale_pdf(sale_base, run, item, sale_number)
                _olympus_pdf(olympus_base, run, item, olympus_number, sale_number)
                attachment_paths = _input_attachment_paths(cursor, item["id"])
                _merge_pdf_documents(sale_path, sale_base, attachment_paths)
                _merge_pdf_documents(olympus_path, olympus_base, attachment_paths)
                for stream, number, path in (("verkoop", sale_number, sale_path), ("olympus", olympus_number, olympus_path)):
                    cursor.execute(
                        """
                        INSERT INTO invoice_outputs (run_id, input_id, stream, invoice_number, file_path, status)
                        VALUES (%s, %s, %s, %s, %s, 'concept')
                        ON CONFLICT (run_id, input_id, stream)
                        DO UPDATE SET invoice_number = EXCLUDED.invoice_number, file_path = EXCLUDED.file_path, updated_at = NOW()
                        RETURNING id;
                        """,
                        (run_id, item["id"], stream, number, str(path),),
                    )
                    output_id = cursor.fetchone()[0]
                    output_ids.append(output_id)
                    cursor.execute(
                        """
                        INSERT INTO invoice_documents
                            (relation_id, principal_id, project_id, run_id, input_id, output_id, agreement_id,
                             document_type, filename, file_path, content_type)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'application/pdf')
                        ON CONFLICT DO NOTHING;
                        """,
                        (item.get("relation_id"), item.get("principal_id"), item.get("project_id"), run_id,
                         item["id"], output_id, item.get("agreement_id"), "verkoopfactuur" if stream == "verkoop" else "olympusfactuur",
                         path.name, str(path)),
                    )
            cursor.execute("UPDATE invoice_runs SET status = 'concept', updated_at = NOW() WHERE id = %s;", (run_id,))
        conn.commit()
    return {"run_id": run_id, "output_ids": output_ids, "count": len(items)}


def get_invoicing_workspace(run_id: int | None = None) -> dict:
    today = date.today()
    fallback = {"runs": [], "selected_run": None, "inputs": [], "outputs": [], "totals": {"sales": "€ 0,00", "olympus": "€ 0,00", "hours": "0", "blockers": 0}, "default_year": today.year, "default_week": today.isocalendar().week, "default_invoice_date": today.isoformat()}
    try:
        _ensure()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT r.id, r.year, r.week_number, r.invoice_date, r.status, COUNT(DISTINCT i.id), COUNT(DISTINCT o.id), r.created_at
                    FROM invoice_runs r
                    LEFT JOIN invoice_inputs i ON i.run_id = r.id
                    LEFT JOIN invoice_outputs o ON o.run_id = r.id
                    WHERE r.status <> 'archief'
                    GROUP BY r.id
                    ORDER BY r.year DESC, r.week_number DESC, r.id DESC
                    LIMIT 30;
                    """
                )
                runs = []
                for row in cursor.fetchall():
                    runs.append({"id": row[0], "year": row[1], "week_number": row[2], "invoice_date": row[3], "invoice_date_text": _date_text(row[3]), "status": row[4], "input_count": row[5], "output_count": row[6], "created_at": row[7]})
                cursor.execute(
                    """
                    SELECT r.id, r.year, r.week_number, r.invoice_date, COUNT(DISTINCT i.id), COUNT(DISTINCT o.id)
                    FROM invoice_runs r
                    LEFT JOIN invoice_inputs i ON i.run_id = r.id
                    LEFT JOIN invoice_outputs o ON o.run_id = r.id
                    WHERE r.status = 'archief'
                    GROUP BY r.id
                    ORDER BY r.year DESC, r.week_number DESC, r.id DESC
                    LIMIT 100;
                    """
                )
                archive_runs = [
                    {"id": row[0], "year": row[1], "week_number": row[2], "invoice_date": row[3],
                     "invoice_date_text": _date_text(row[3]), "input_count": row[4], "output_count": row[5]}
                    for row in cursor.fetchall()
                ]
                agreements = list_invoice_agreements()
                selected_id = run_id or (runs[0]["id"] if runs else None)
                selected_run = next((item for item in runs if item["id"] == selected_id), None)
                inputs = []
                outputs = []
                if selected_run:
                    cursor.execute("SELECT id FROM invoice_inputs WHERE run_id = %s ORDER BY id;", (selected_id,))
                    inputs = [_input_row(cursor, row[0]) for row in cursor.fetchall()]
                    cursor.execute(
                        """
                        SELECT o.id, o.input_id, o.stream, o.invoice_number, o.status, o.file_path,
                               COALESCE(i.employee_name, '')
                        FROM invoice_outputs o
                        LEFT JOIN invoice_inputs i ON i.id = o.input_id
                        WHERE o.run_id = %s
                        ORDER BY i.employee_name, o.input_id, o.stream;
                        """,
                        (selected_id,),
                    )
                    outputs = [
                        {"id": row[0], "input_id": row[1], "stream": row[2], "invoice_number": row[3],
                         "status": row[4], "filename": Path(row[5]).name, "employee_name": row[6]}
                        for row in cursor.fetchall()
                    ]
                total_sales = sum((_money(item["sales_total_including_vat"]) for item in inputs), Decimal("0"))
                total_olympus = sum((_money(item["olympus_total"]) for item in inputs), Decimal("0"))
                total_hours = sum((_decimal(item["hours"]) for item in inputs), Decimal("0"))
                return {"runs": runs, "archive_runs": archive_runs, "agreements": agreements, "selected_run": selected_run, "inputs": inputs, "outputs": outputs, "totals": {"sales": _money_text(total_sales), "olympus": _money_text(total_olympus), "hours": _number_text(total_hours), "blockers": sum(len(item["blockers"]) for item in inputs)}, "default_year": today.year, "default_week": today.isocalendar().week, "default_invoice_date": today.isoformat()}
    except Exception as exc:
        print(f"INVOICING_CONTEXT_ERROR {type(exc).__name__}: {exc}")
        fallback.update({"archive_runs": [], "agreements": []})
        return fallback
