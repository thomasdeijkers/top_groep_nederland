from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from apps.dashboard.data_store import ensure_dashboard_tables
from shared.db.connection import get_connection


INVOICE_EXPORT_DIR = Path("runtime/exports/invoicing")
DEFAULT_FEE_PERCENT = Decimal("13.25")
FACTORING_FEE_PERCENT = Decimal("12.50")
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


def _lookup_names(cursor, relation_id, principal_id, project_id) -> dict:
    names = {"employee_name": "", "principal_name": "", "project_name": "", "project_reference": ""}
    if relation_id:
        cursor.execute("SELECT name, COALESCE(external_id, '') FROM relations WHERE id = %s AND relation_type = 'candidate';", (relation_id,))
        row = cursor.fetchone()
        if row:
            names["employee_name"] = row[0] or ""
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
    hourly_rate = _money(data.get("hourly_rate"))
    agreed_amount = _money(data.get("agreed_amount"))
    labor_amount = _effective_amount(regime, hours, hourly_rate, agreed_amount)
    factoring = bool(data.get("factoring"))
    supplied_fee = str(data.get("fee_percent") or "").strip()
    services = str(data.get("services") or ("a,b,c" if factoring else "a,b,c,d"))
    if factoring and not supplied_fee and services == "a,b,c,d":
        services = "a,b,c"
    fee_percent = _money(supplied_fee or (FACTORING_FEE_PERCENT if factoring else DEFAULT_FEE_PERCENT))
    _ensure()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            names = _lookup_names(cursor, data.get("relation_id"), data.get("principal_id"), data.get("project_id"))
            cursor.execute(
                """
                INSERT INTO invoice_inputs (
                    run_id, relation_id, principal_id, project_id,
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
                    %s, %s, %s, %s,
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
                    run_id, data.get("relation_id") or None, data.get("principal_id") or None, data.get("project_id") or None,
                    names["employee_name"] or str(data.get("employee_name") or "").strip(),
                    names["principal_name"] or str(data.get("principal_name") or "").strip(),
                    names["project_name"] or str(data.get("project_name") or "").strip(),
                    names["project_reference"] or str(data.get("project_reference") or "").strip(),
                    names.get("project_location", "") or str(data.get("project_location") or "").strip(),
                    regime, hours, hourly_rate, agreed_amount, labor_amount,
                    _money(data.get("parking_costs")), _money(data.get("material_costs")), _money(data.get("other_sales_costs")),
                    _money(data.get("olympus_costs")), str(data.get("olympus_cost_description") or "Olympus-kosten").strip(),
                    _money(data.get("sales_vat_rate")), fee_percent, services,
                    bool(data.get("sepa_active")), factoring, str(data.get("factoring_company") or "Pronkert Factoring B.V.").strip(),
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
                UPDATE invoice_inputs
                SET regime = %s, hours = %s, hourly_rate = %s, agreed_amount = %s, labor_amount = %s,
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
        SELECT i.id, i.run_id, i.relation_id, i.principal_id, i.project_id,
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
        "id", "run_id", "relation_id", "principal_id", "project_id", "employee_name", "principal_name", "project_name",
        "project_reference", "project_location", "regime", "hours", "hourly_rate", "agreed_amount", "labor_amount",
        "parking_costs", "material_costs", "other_sales_costs", "olympus_costs", "olympus_cost_description",
        "sales_vat_rate", "fee_percent", "services", "sepa_active", "factoring", "factoring_company", "factoring_iban",
        "factoring_address", "factoring_city", "factoring_email", "factoring_phone", "factoring_kvk", "supplier_invoice_number",
        "supplier_invoice_suffix", "payment_term_days", "source_type", "status", "notes",
    )
    item = dict(zip(keys, row))
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


def _services_text(item: dict) -> str:
    services = [part.strip().lower() for part in str(item.get("services") or "").split(",") if part.strip()]
    return f"3.1 {', '.join(services)}" if services and services != ["a", "b", "c", "d"] else "optionele diensten art. 3.1"


def _address_block(c, x: float, y: float, title: str, lines: list[str]) -> None:
    colors, _, _ = _reportlab_dependencies()
    c.setFillColor(colors.HexColor("#16372b"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(x, y, title.upper())
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 10)
    cursor_y = y - 16
    for line in lines:
        if line:
            c.drawString(x, cursor_y, str(line))
            cursor_y -= 14


def _invoice_header(c, title: str, subtitle: str, number: str) -> None:
    colors, A4, _ = _reportlab_dependencies()
    width, height = A4
    c.setFillColor(colors.HexColor("#102b24"))
    c.rect(0, height - 86, width, 86, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#eaf6ef"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(42, height - 42, title)
    c.setFont("Helvetica", 9)
    c.drawString(44, height - 60, subtitle)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 42, height - 42, f"FACTUUR {number}")


def _line(c, y: float, label: str, value: str, amount: str, width: float) -> float:
    colors, _, _ = _reportlab_dependencies()
    c.setStrokeColor(colors.HexColor("#d7e1dc"))
    c.line(42, y - 5, width - 42, y - 5)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 10)
    c.drawString(48, y - 1, label)
    if value:
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#6b777d"))
        c.drawString(48, y - 14, value)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 48, y - 1, amount)
    return y - (30 if value else 22)


def _sale_pdf(path: Path, run: dict, item: dict, invoice_number: str) -> None:
    colors, A4, canvas = _reportlab_dependencies()
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    _invoice_header(c, "FACTUUR", "Verkoopfactuur namens de zzp'er", invoice_number)
    _address_block(c, 42, height - 122, "Aan opdrachtgever", [item["principal_name"], "Per factuur-e-mail", item["project_location"]])
    _address_block(c, 320, height - 122, "Afzender", [item["employee_name"], "Zzp'er / opdrachtnemer", "OBS-code wordt aan de overeenkomst ontleend"])
    c.setFillColor(colors.HexColor("#eef4f0"))
    c.roundRect(42, height - 274, width - 84, 74, 6, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    meta = [
        ("Factuur", invoice_number), ("Datum", _date_text(run["invoice_date"])),
        ("Week", f"{run['week_number']} {run['year']}"), ("Project", item["project_name"]),
        ("Werk", item["project_reference"] or "-"), ("Regime", item["regime"]),
    ]
    for index, (label, value) in enumerate(meta):
        x = 52 + (index % 2) * 265
        y = height - 222 - (index // 2) * 22
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x, y, f"{label}:")
        c.setFont("Helvetica", 9)
        c.drawString(x + 54, y, str(value)[:44])
    y = height - 314
    c.setFillColor(colors.HexColor("#16372b"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(48, y, "Werkzaamheden en doorbelastingen")
    y -= 28
    obs_code = f"ZZP OBS {item.get('relation_id') or '-'} {item.get('principal_id') or '-'}"
    y = _line(c, y, "Uitgevoerde werkzaamheden conform overeenkomst", obs_code, _money_text(item["labor_amount"]), width)
    y = _line(c, y, "Doorbelaste parkeerkosten", "Declaratiebedrag exclusief btw", _money_text(item["parking_costs"]), width)
    y = _line(c, y, "Doorbelaste materiaalkosten", "Declaratiebedrag exclusief btw", _money_text(item["material_costs"]), width)
    if _money(item["other_sales_costs"]):
        y = _line(c, y, "Overige eenmalige doorbelasting", "Aanvullende kostenregel", _money_text(item["other_sales_costs"]), width)
    c.setFillColor(colors.HexColor("#102b24"))
    c.rect(42, y - 32, width - 84, 32, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(52, y - 20, "Totaal door u te voldoen")
    c.drawRightString(width - 52, y - 20, _money_text(item["sales_total_including_vat"]))
    y -= 58
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    if _decimal(item["sales_vat_rate"]) == 0:
        c.drawString(48, y, "De btw-verleggingsregeling is van toepassing.")
    else:
        c.drawString(48, y, f"Btw 21%: {_money_text(item['sales_vat'])} over {_money_text(item['sales_total'])}.")
    y -= 28
    payment_date = run["invoice_date"] + timedelta(days=int(item["payment_term_days"] or 30))
    if item["factoring"]:
        c.setFillColor(colors.HexColor("#7b1e1e"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(48, y, f"Betaling van deze vordering uiterlijk {_date_text(payment_date)} op rekening van {item['factoring_company']}.")
        y -= 15
        c.setFont("Helvetica", 9)
        c.drawString(48, y, f"IBAN: {item['factoring_iban'] or '-'} | onder vermelding van factuurnummer {invoice_number}")
        y -= 40
        c.setFillColor(colors.HexColor("#fff0f0"))
        c.roundRect(42, y - 70, width - 84, 70, 6, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#7b1e1e"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(54, y - 22, "FACTORING")
        c.setFont("Helvetica", 9)
        c.drawString(54, y - 39, f"{item['employee_name']} maakt gebruik van factoring.")
        c.drawString(54, y - 54, f"De vordering is overgedragen aan {item['factoring_company']}.")
    else:
        c.drawString(48, y, f"Betaling uiterlijk {_date_text(payment_date)} op de rekening van de zzp'er.")
    c.setFillColor(colors.HexColor("#6b777d"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 34, "Factuur opgesteld namens de zzp'er. Doorbelaste bedragen zijn exclusief btw opgenomen.")
    c.save()


def _olympus_pdf(path: Path, run: dict, item: dict, invoice_number: str, sale_invoice_number: str) -> None:
    colors, A4, canvas = _reportlab_dependencies()
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    _invoice_header(c, "OLYMPUS", "Factuur dienstverlening Olympus Bouw B.V.", invoice_number)
    _address_block(c, 42, height - 122, "Aan zzp'er", [item["employee_name"], "Debiteurnummer: " + str(item.get("relation_id") or "-"), "Factuur voor dienstverlening"])
    _address_block(c, 320, height - 122, "Olympus Bouw B.V.", ["Hoofdweg 242/244", "2908 LC Capelle aan den IJssel", "info@olympusbouw.nl"])
    c.setFillColor(colors.HexColor("#eef4f0"))
    c.roundRect(42, height - 254, width - 84, 54, 6, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    c.drawString(52, height - 222, f"Project: {item['project_name'] or '-'}")
    c.drawString(320, height - 222, f"Week: {run['week_number']} {run['year']} | Datum: {_date_text(run['invoice_date'])}")
    y = height - 292
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 10)
    c.drawString(48, y, "Hierbij brengen wij u in rekening de aan u geleverde optionele dienstverlening")
    c.drawString(48, y - 15, "op basis van onze goedgekeurde bemiddelingsovereenkomst.")
    y -= 54
    c.setFillColor(colors.HexColor("#16372b"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(48, y, "Dienstverlening")
    y -= 28
    y = _line(c, y, f"Door u reeds gefactureerd met factuurnummer {sale_invoice_number}", f"Week {run['week_number']} {run['year']}", _money_text(item["sales_total_including_vat"]), width)
    y = _line(c, y, f"Aan u geleverde {_services_text(item)}", "Fee over alleen de arbeidsomzet", _money_text(item["fee_amount"]), width)
    y = _line(c, y, "Berekend over de omzet onder aftrek van e.v.t. door u doorbelaste kosten", "Arbeidsomzet", _money_text(item["labor_amount"]), width)
    if item["admin_fee"]:
        y = _line(c, y, "Administratievergoeding wegens geen SEPA-incasso", "Exclusief btw", _money_text(item["admin_fee"]), width)
    if _money(item["olympus_costs"]):
        y = _line(c, y, item["olympus_cost_description"] or "Door ons aan u doorbelaste kosten", "Btw 0%", _money_text(item["olympus_costs"]), width)
    y -= 8
    y = _line(c, y, "Verschuldigde 21% btw", "Over fee en administratievergoeding", _money_text(item["olympus_vat"]), width)
    c.setFillColor(colors.HexColor("#102b24"))
    c.rect(42, y - 32, width - 84, 32, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(52, y - 20, "Totaal te voldoen")
    c.drawRightString(width - 52, y - 20, _money_text(item["olympus_total"]))
    y -= 62
    debit_days = 8 if item["factoring"] else 30
    debit_date = run["invoice_date"] + timedelta(days=debit_days)
    c.setFillColor(colors.HexColor("#27333a"))
    c.setFont("Helvetica", 9)
    c.drawString(48, y, f"Het totaalbedrag wordt afgeschreven op {_date_text(debit_date)} van uw rekening.")
    c.drawString(48, y - 15, "SEPA-incasso: " + ("actief" if item["sepa_active"] else "niet actief; betaal de factuur zelf"))
    c.setFillColor(colors.HexColor("#6b777d"))
    c.setFont("Helvetica", 8)
    c.drawString(42, 34, "Olympus Bouw B.V. | Factuurreeks doorlopend beheerd | Alle bedragen in euro's")
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
                sale_number = _output_number(cursor, run_id, item["id"], "verkoop") or _supplier_invoice_number(item)
                olympus_number = _output_number(cursor, run_id, item["id"], "olympus") or _next_olympus_number(cursor)
                sale_path = INVOICE_EXPORT_DIR / f"verkoopfactuur_{run_id}_{item['id']}_{sale_number.replace('/', '-')}.pdf"
                olympus_path = INVOICE_EXPORT_DIR / f"olympusfactuur_{run_id}_{item['id']}_{olympus_number}.pdf"
                _sale_pdf(sale_path, run, item, sale_number)
                _olympus_pdf(olympus_path, run, item, olympus_number, sale_number)
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
                    output_ids.append(cursor.fetchone()[0])
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
                    GROUP BY r.id
                    ORDER BY r.year DESC, r.week_number DESC, r.id DESC
                    LIMIT 30;
                    """
                )
                runs = []
                for row in cursor.fetchall():
                    runs.append({"id": row[0], "year": row[1], "week_number": row[2], "invoice_date": row[3], "invoice_date_text": _date_text(row[3]), "status": row[4], "input_count": row[5], "output_count": row[6], "created_at": row[7]})
                selected_id = run_id or (runs[0]["id"] if runs else None)
                selected_run = next((item for item in runs if item["id"] == selected_id), None)
                inputs = []
                outputs = []
                if selected_run:
                    cursor.execute("SELECT id FROM invoice_inputs WHERE run_id = %s ORDER BY id;", (selected_id,))
                    inputs = [_input_row(cursor, row[0]) for row in cursor.fetchall()]
                    cursor.execute("SELECT id, input_id, stream, invoice_number, status, file_path FROM invoice_outputs WHERE run_id = %s ORDER BY input_id, stream;", (selected_id,))
                    outputs = [{"id": row[0], "input_id": row[1], "stream": row[2], "invoice_number": row[3], "status": row[4], "filename": Path(row[5]).name} for row in cursor.fetchall()]
                total_sales = sum((_money(item["sales_total_including_vat"]) for item in inputs), Decimal("0"))
                total_olympus = sum((_money(item["olympus_total"]) for item in inputs), Decimal("0"))
                total_hours = sum((_decimal(item["hours"]) for item in inputs), Decimal("0"))
                return {"runs": runs, "selected_run": selected_run, "inputs": inputs, "outputs": outputs, "totals": {"sales": _money_text(total_sales), "olympus": _money_text(total_olympus), "hours": _number_text(total_hours), "blockers": sum(len(item["blockers"]) for item in inputs)}, "default_year": today.year, "default_week": today.isocalendar().week, "default_invoice_date": today.isoformat()}
    except Exception as exc:
        print(f"INVOICING_CONTEXT_ERROR {type(exc).__name__}: {exc}")
        return fallback
