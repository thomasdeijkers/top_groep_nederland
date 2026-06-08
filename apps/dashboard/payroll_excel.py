import re
from pathlib import Path

from apps.dashboard.payroll_calculations import PAYSLIP_SHEET_COLUMNS, PERIOD_SHEET_COLUMNS


WEEK_SHEET_RE = re.compile(r"^WK\s*(\d{1,2})$", re.IGNORECASE)
PERIOD_SHEET = "periode"
PAYSLIP_SHEET = "loonstrook"
FOUNDATION_KEYWORDS = ("grondslag", "savg", "cao", "pensioen", "reservering")

WEEK_FIELD_ALIASES = {
    "employee_name": ("werknemer", "naam werknemer", "kandidaat"),
    "contract_hours": ("contract uren", "contracturen"),
    "worked_days": ("dagen gewerkt", "gewerkte dagen"),
    "worked_hours": ("uren gewerkt", "gewerkte uren"),
    "vacation_hours": ("vak opname", "vakantie", "vakantie-opname"),
    "sickness_hours": ("ziek opname", "ziekte", "ziekte-uren"),
    "rv_hours": ("rv opname", "roostervrij", "rv"),
    "kv_hours": ("kv/c doorbetaald", "kort verzuim", "kv"),
    "holiday_hours": ("fd doorbetaald", "feestdagen", "fd"),
    "net_amount": ("netto bedrag", "netto"),
    "commute_km": ("km woon-werk", "kilometers enkele reis", "enkele reis"),
    "work_km": ("km werk",),
    "total_km": ("totaal km", "kilometers"),
    "fuel_amount": ("brandstofbedrag", "brandstof"),
    "extra_reimbursement": ("extra declaratie", "vergoeding", "declaratie"),
    "net_advance": ("netto voorschot", "voorschot"),
    "remarks": ("opmerking", "opmerkingen"),
    "project_info": ("actueel project", "project"),
}

PERIOD_FIELD_ALIASES = {
    "employee_name": ("werknemer", "kandidaat"),
    "license_plate": ("kenteken",),
    "choice_budget": ("keuzebudget",),
    "phase": ("fase",),
    "pension_scheme": ("pensioen",),
    "contract_hours": ("contracturen", "contract uren"),
    "cao_name": ("cao",),
    "days_right": ("recht op dagen",),
    "configuration": ("inregeling",),
    "function_name": ("functie",),
    "gross_hourly_wage": ("bruto uurloon",),
    "gross_total": ("bruto totaal",),
    "reservations": ("reserveringen",),
}

PAYSLIP_FIELD_ALIASES = {
    "employee_name": ("werknemer",),
    "cao_name": ("cao",),
    "total_worked_days": ("totale dagen gewerkt", "dagen gewerkt"),
    "total_worked_hours": ("totale uren gewerkt", "uren gewerkt"),
    "total_vacation_hours": ("totaal vak", "vakantie"),
    "total_sickness_hours": ("totaal ziek", "ziek"),
    "total_rv_hours": ("totaal rv",),
    "total_kv_hours": ("totaal kv",),
    "total_holiday_hours": ("totaal fd",),
    "total_km": ("totaal kilometers", "totaal km"),
    "extra_reimbursements": ("extra declaraties", "extra vergoeding"),
    "already_received_net": ("reeds ontvangen netto",),
    "net_to_receive": ("nog te ontvangen netto", "nog te ontvangen netto loon"),
    "period_total": ("totaal 4 weken",),
    "wkr_reimbursements": ("wkr vergoedingen",),
    "payslip_advance": ("loonvoorschot strook",),
}


def analyze_payroll_workbook(path: str | Path) -> dict:
    workbook_path = Path(path)
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is nodig om Excel-bestanden te analyseren.") from exc

    workbook = load_workbook(workbook_path, data_only=False, read_only=False)
    sheet_names = workbook.sheetnames
    week_tabs = []
    foundation_tabs = []
    mapped_fields = {}
    formulas = []
    warnings = []

    for sheet_name in sheet_names:
        normalized = _normalize(sheet_name)
        week_match = WEEK_SHEET_RE.match(sheet_name.strip())
        worksheet = workbook[sheet_name]
        if week_match:
            week_tabs.append({"sheet": sheet_name, "week_number": int(week_match.group(1))})
            mapped_fields[sheet_name] = _map_headers(worksheet, WEEK_FIELD_ALIASES)
        elif normalized == PERIOD_SHEET:
            mapped_fields[sheet_name] = _map_headers(worksheet, PERIOD_FIELD_ALIASES)
        elif normalized == PAYSLIP_SHEET:
            mapped_fields[sheet_name] = _map_headers(worksheet, PAYSLIP_FIELD_ALIASES)
        elif any(keyword in normalized for keyword in FOUNDATION_KEYWORDS):
            foundation_tabs.append(sheet_name)
            mapped_fields[sheet_name] = _map_headers(worksheet, PERIOD_FIELD_ALIASES | PAYSLIP_FIELD_ALIASES)
        formulas.extend(_collect_formulas(worksheet, sheet_name))

    if not week_tabs:
        warnings.append("Geen weektabs met patroon WKxx gevonden.")
    if not any(_normalize(name) == PERIOD_SHEET for name in sheet_names):
        warnings.append("Tabblad Periode niet gevonden.")
    if not any(_normalize(name) == PAYSLIP_SHEET for name in sheet_names):
        warnings.append("Tabblad Loonstrook niet gevonden.")

    return {
        "filename": workbook_path.name,
        "sheet_names": sheet_names,
        "week_tabs": sorted(week_tabs, key=lambda item: item["week_number"]),
        "period_sheet": _first_matching_sheet(sheet_names, PERIOD_SHEET),
        "payslip_sheet": _first_matching_sheet(sheet_names, PAYSLIP_SHEET),
        "foundation_sheets": foundation_tabs,
        "mapped_fields": mapped_fields,
        "formulas": formulas[:250],
        "formula_count": len(formulas),
        "warnings": warnings,
    }


def _first_matching_sheet(sheet_names: list[str], normalized_name: str) -> str | None:
    return next((name for name in sheet_names if _normalize(name) == normalized_name), None)


def _normalize(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _map_headers(worksheet, aliases: dict[str, tuple[str, ...]]) -> dict:
    mapped = {}
    for row in worksheet.iter_rows(min_row=1, max_row=min(40, worksheet.max_row), max_col=min(80, worksheet.max_column)):
        for cell in row:
            text = _normalize(cell.value)
            if not text:
                continue
            for field_key, labels in aliases.items():
                if field_key in mapped:
                    continue
                if any(label in text for label in labels):
                    mapped[field_key] = {"label": str(cell.value), "cell": cell.coordinate}
    return mapped


def _collect_formulas(worksheet, sheet_name: str) -> list[dict]:
    formulas = []
    for row in worksheet.iter_rows():
        for cell in row:
            value = cell.value
            if isinstance(value, str) and value.startswith("="):
                formulas.append({"sheet": sheet_name, "cell": cell.coordinate, "formula": value})
    return formulas


def build_payroll_output_workbook(path: str | Path, period: dict) -> Path:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is nodig om Excel-output te maken.") from exc

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    workbook.remove(workbook.active)
    tabs = period.get("workbook_tabs") or [
        {"label": "Periode", "columns": PERIOD_SHEET_COLUMNS, "rows": period.get("period_sheet_rows", [])},
        {"label": "Loonstrook", "columns": PAYSLIP_SHEET_COLUMNS, "rows": period.get("payslip_sheet_rows", [])},
    ]
    for tab in tabs:
        worksheet = workbook.create_sheet(str(tab.get("label") or "Tabblad")[:31])
        _write_sheet(worksheet, tab.get("columns", []), tab.get("rows", []))
    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(horizontal="center")
        tab = next((item for item in tabs if str(item.get("label") or "Tabblad")[:31] == worksheet.title), {})
        for index, column in enumerate(tab.get("columns", []), start=1):
            if column.get("hidden_in_excel"):
                worksheet.column_dimensions[get_column_letter(index)].hidden = True
        for column in worksheet.columns:
            width = max(len(str(cell.value or "")) for cell in column)
            worksheet.column_dimensions[get_column_letter(column[0].column)].width = min(max(width + 2, 12), 34)
    workbook.save(output_path)
    return output_path


def _write_sheet(worksheet, columns: list[dict], rows: list[dict]) -> None:
    worksheet.append([column["label"] for column in columns])
    for row in rows:
        worksheet.append([row.get(column["key"], "") for column in columns])
