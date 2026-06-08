from decimal import Decimal, InvalidOperation


DEFAULT_RULES = [
    {
        "rule_key": "period_total_worked_hours",
        "name": "Totaal gewerkte uren",
        "category": "periode",
        "expression": "Som van gewerkte uren uit gekoppelde weekregels binnen de loonperiode.",
        "status": "actief",
        "notes": "Gebaseerd op bestaande urenverwerking en projectboekingen.",
    },
    {
        "rule_key": "period_gross_reference",
        "name": "Bruto indicatie",
        "category": "loonstrook",
        "expression": "Totaal uren maal bruto uurloon waar beschikbaar.",
        "status": "concept",
        "notes": "Moet worden gevalideerd tegen Excel-tab Loonstrook en cao-regels.",
    },
    {
        "rule_key": "net_to_receive_reference",
        "name": "Nog te ontvangen netto",
        "category": "netto",
        "expression": "Excel-referentie minus reeds ontvangen netto en voorschotten.",
        "status": "handmatig_controleren",
        "notes": "Fiscale en pensioenlogica blijft controleplichtig totdat regels zijn gevalideerd.",
    },
]


def default_calculation_rules() -> list[dict]:
    return DEFAULT_RULES


def build_period_sheet_rows(candidates: list[dict], payroll_rows: list[dict]) -> list[dict]:
    payroll_by_name = {
        _key(row.get("employee_name")): row
        for row in payroll_rows
        if row.get("employee_name")
    }
    rows = []
    for index, candidate in enumerate(candidates, start=1):
        payroll_row = payroll_by_name.get(_key(candidate.get("name")), {})
        hourly_wage = _decimal(candidate.get("hourly_rate")) or _decimal(payroll_row.get("hourly_wage")) or Decimal("21.50")
        contract_hours = Decimal("40") if index % 3 else Decimal("32")
        cao_name = payroll_row.get("cao_name") or ("Bouw & Infra" if index % 2 else "SAVG")
        phase = "B" if index % 2 else "A"
        reservation_percent = Decimal("18.5") if cao_name.lower().startswith("bouw") else Decimal("16.0")
        bruto_total = hourly_wage * contract_hours
        rows.append(
            {
                "employee_name": candidate.get("name") or "-",
                "license_plate": _dummy_license_plate(index),
                "choice_budget": "Ja" if index % 2 else "Nee",
                "phase": phase,
                "pension_scheme": "StiPP Basis" if phase == "A" else "StiPP Plus",
                "contract_hours": _format_number(contract_hours),
                "cao_name": cao_name,
                "days_right": "20",
                "configuration": "Concept",
                "function_name": candidate.get("notes") or "Medewerker bouw",
                "gross_hourly_wage": _format_money(hourly_wage),
                "gross_total": _format_money(bruto_total),
                "reservations": f"{_format_number(reservation_percent)}%",
                "net_period_basis": _format_money(bruto_total * Decimal("0.62")),
                "period_basis": "4 weken",
                "reservation_basis": f"{cao_name} concept",
                "source": "echte kandidaat + dummy looninstellingen",
                "status": "dummy",
            }
        )
    return rows


def build_payslip_sheet_rows(period_rows: list[dict], total_rows: list[dict]) -> list[dict]:
    totals_by_name = {
        _key(row.get("employee_name")): row
        for row in total_rows
        if row.get("employee_name")
    }
    rows = []
    for period_row in period_rows:
        totals = totals_by_name.get(_key(period_row.get("employee_name")), {})
        worked_hours = _decimal(totals.get("total_worked_hours"))
        worked_days = _decimal(totals.get("total_worked_days"))
        hourly_wage = _decimal(period_row.get("gross_hourly_wage"))
        km_total = _decimal(totals.get("total_km"))
        declarations = _decimal(totals.get("total_declarations"))
        net_advance = _decimal(totals.get("total_net_advance"))
        gross_reference = worked_hours * hourly_wage
        travel_allowance = km_total * Decimal("0.23")
        net_reference = (gross_reference * Decimal("0.62")) + travel_allowance + declarations
        net_to_receive = max(net_reference - net_advance, Decimal("0"))
        rows.append(
            {
                "employee_name": period_row.get("employee_name"),
                "cao_name": period_row.get("cao_name"),
                "total_worked_days": _format_number(worked_days),
                "total_worked_hours": _format_number(worked_hours),
                "total_vacation_hours": totals.get("total_vacation_hours", "0"),
                "total_sickness_hours": totals.get("total_sickness_hours", "0"),
                "total_rv_hours": totals.get("total_rv_hours", "0"),
                "total_kv_hours": totals.get("total_kv_hours", "0"),
                "total_holiday_hours": totals.get("total_holiday_hours", "0"),
                "total_km": _format_number(km_total),
                "extra_reimbursements": _format_money(declarations),
                "already_received_net": _format_money(net_advance),
                "net_to_receive": _format_money(net_to_receive),
                "period_total": _format_money(net_reference),
                "wkr_reimbursements": _format_money(travel_allowance),
                "payslip_advance": _format_money(net_advance),
                "status": "concept",
            }
        )
    return rows


def derived_period_total_rows(payroll_rows: list[dict]) -> list[dict]:
    rows = []
    for row in payroll_rows:
        total_hours = _decimal(row.get("total_hours"))
        gross_amount = _money_decimal(row.get("gross_amount"))
        rows.append(
            {
                "employee_name": row.get("employee_name") or "-",
                "total_worked_days": row.get("worked_days") or 0,
                "total_worked_hours": _format_number(total_hours),
                "total_vacation_hours": "0",
                "total_sickness_hours": "0",
                "total_rv_hours": "0",
                "total_kv_hours": "0",
                "total_holiday_hours": "0",
                "total_km": "0",
                "total_declarations": "0,00",
                "total_net_advance": "0,00",
                "already_received_net": "0,00",
                "net_to_receive": "0,00",
                "total_period_amount": _format_money(gross_amount),
                "wkr_reimbursements": "0,00",
                "status": "concept",
                "source": "urenverwerking",
            }
        )
    return rows


def compare_values(excel_value, dashboard_value, tolerance=Decimal("0.05")) -> dict:
    excel_decimal = _decimal(excel_value)
    dashboard_decimal = _decimal(dashboard_value)
    difference = dashboard_decimal - excel_decimal
    return {
        "excel_value": _format_number(excel_decimal),
        "dashboard_value": _format_number(dashboard_decimal),
        "difference": _format_number(difference),
        "status": "akkoord" if abs(difference) <= tolerance else "verschil",
    }


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    text = str(value or "0").replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _key(value) -> str:
    return str(value or "").strip().lower()


def _dummy_license_plate(index: int) -> str:
    return f"TGN-{index:03d}"


def _money_decimal(value) -> Decimal:
    return _decimal(value)


def _format_number(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01"))
    if normalized == normalized.to_integral():
        return str(normalized.to_integral())
    return str(normalized).replace(".", ",")


def _format_money(value: Decimal) -> str:
    return f"€ {value.quantize(Decimal('0.01'))}".replace(".", ",")
