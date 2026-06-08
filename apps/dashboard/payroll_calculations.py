from decimal import Decimal, InvalidOperation


WEEK_SHEET_COLUMNS = [
    {"label": "Werknemer", "key": "employee_name"},
    {"label": "Contract uren", "key": "contract_hours"},
    {"label": "Dagen gewerkt", "key": "worked_days"},
    {"label": "Uren gewerkt", "key": "worked_hours"},
    {"label": "VAK opname", "key": "vacation_hours"},
    {"label": "ZIEK opname", "key": "sickness_hours"},
    {"label": "RV opname", "key": "rv_hours"},
    {"label": "KV/C doorbetaald", "key": "kv_hours"},
    {"label": "FD doorbetaald", "key": "holiday_hours"},
    {"label": "Netto bedrag", "key": "net_amount"},
    {"label": "Km woon-werk", "key": "commute_km"},
    {"label": "Km werk", "key": "work_km"},
    {"label": "Totaal km", "key": "total_km"},
    {"label": "Brandstofbedrag", "key": "fuel_amount"},
    {"label": "Extra declaratie/vergoeding", "key": "extra_reimbursement"},
    {"label": "Netto voorschot", "key": "net_advance"},
    {"label": "Opmerking", "key": "remarks"},
    {"label": "Actueel project", "key": "project_info"},
    {"label": "Kilometers enkele reis", "key": "single_trip_km"},
    {"label": "Controle uren", "key": "hours_check", "hidden_in_excel": True},
    {"label": "Controle km", "key": "km_check", "hidden_in_excel": True},
    {"label": "Bron", "key": "source", "hidden_in_excel": True},
]

PERIOD_SHEET_COLUMNS = [
    {"label": "Werknemer", "key": "employee_name"},
    {"label": "Kenteken", "key": "license_plate"},
    {"label": "Keuzebudget", "key": "choice_budget"},
    {"label": "Fase", "key": "phase", "options": ["Fase A", "Fase B", "Fase C", "Fase 1-2", "Fase 3"]},
    {"label": "Pensioen", "key": "pension_scheme", "options": ["BPF UTA", "BPF Bouw", "StiPP Basis", "StiPP Plus", "Geen"]},
    {"label": "Uren CAO", "key": "contract_hours"},
    {"label": "Recht op dagen", "key": "days_right"},
    {"label": "Inregeling", "key": "configuration", "options": ["B.02.1 Aannemingschaal 2", "T4.2 F/G A", "T4.58 Particulier halfjaar", "Concept"]},
    {"label": "Functie", "key": "function_name"},
    {"label": "Bruto uurloon", "key": "gross_hourly_wage"},
    {"label": "Bruto totaal", "key": "gross_total"},
    {"label": "BIK", "key": "bik"},
    {"label": "D-BIK / Vgel", "key": "wage_component"},
    {"label": "Reservering VAK dagen", "key": "reserve_vacation_days"},
    {"label": "Reservering ADV", "key": "reserve_adv"},
    {"label": "Reservering feest", "key": "reserve_holiday"},
    {"label": "TSF", "key": "tsf"},
    {"label": "Vak.geld", "key": "holiday_allowance"},
    {"label": "RV flex", "key": "rv_flex"},
    {"label": "Compensatie UTA dagen", "key": "compensation_uta_days"},
    {"label": "Compensatie ADV dagen", "key": "compensation_adv_days"},
    {"label": "Compensatie T", "key": "compensation_t"},
    {"label": "Pensioen component", "key": "pension_component"},
    {"label": "Loonkosten / marge", "key": "labor_cost_margin"},
    {"label": "Uitzendfactor", "key": "staffing_factor"},
    {"label": "Netto-/periodegrondslag", "key": "net_period_basis"},
    {"label": "Periodegrondslag", "key": "period_basis"},
    {"label": "Reserveringsgrondslag", "key": "reservation_basis"},
    {"label": "Status", "key": "status", "options": ["dummy", "concept", "gecontroleerd", "akkoord"]},
    {"label": "Controlekolom Excel", "key": "excel_control", "hidden_in_excel": True},
    {"label": "Bron", "key": "source", "hidden_in_excel": True},
]

PAYSLIP_SHEET_COLUMNS = [
    {"label": "Werknemer", "key": "employee_name"},
    {"label": "CAO", "key": "cao_name", "options": ["UTA", "SAVG", "Bouw & Infra", "Bouw", "Geen"]},
    {"label": "Totale dagen gewerkt", "key": "total_worked_days"},
    {"label": "Totale uren gewerkt", "key": "total_worked_hours"},
    {"label": "Totaal VAK", "key": "total_vacation_hours"},
    {"label": "Totaal Ziek", "key": "total_sickness_hours"},
    {"label": "Totaal RV", "key": "total_rv_hours"},
    {"label": "Totaal KV", "key": "total_kv_hours"},
    {"label": "Totaal FD", "key": "total_holiday_hours"},
    {"label": "Totaal kilometers", "key": "total_km"},
    {"label": "Extra declaraties/vergoeding", "key": "extra_reimbursements"},
    {"label": "Reeds ontvangen netto", "key": "already_received_net"},
    {"label": "Nog te ontvangen netto loon", "key": "net_to_receive"},
    {"label": "Totaal 4 weken", "key": "period_total"},
    {"label": "WKR vergoedingen", "key": "wkr_reimbursements"},
    {"label": "Loonvoorschot strook", "key": "payslip_advance"},
    {"label": "Bruto loon", "key": "gross_wage"},
    {"label": "Inhouding pensioen", "key": "pension_deduction"},
    {"label": "Inhouding loonheffing", "key": "payroll_tax"},
    {"label": "Netto na inhoudingen", "key": "net_after_deductions"},
    {"label": "GV", "key": "gv"},
    {"label": "VKR", "key": "vkr"},
    {"label": "IK", "key": "ik"},
    {"label": "TOTAAL NETTO", "key": "net_total"},
    {"label": "Auto/kenteken", "key": "car_license_plate"},
    {"label": "Wk loon", "key": "weekly_wage"},
    {"label": "NTF SL", "key": "ntf_sl"},
    {"label": "BKP NTFSL", "key": "bkp_ntfsl"},
    {"label": "Ziekte", "key": "sickness_value"},
    {"label": "Personeelskosten", "key": "personnel_costs"},
    {"label": "Notitie", "key": "notes"},
    {"label": "Status", "key": "status", "options": ["concept", "gecontroleerd", "akkoord"]},
    {"label": "Controlekolom Excel", "key": "excel_control", "hidden_in_excel": True},
]


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


def build_workbook_tabs(period_weeks: list[dict], candidates: list[dict], payroll_rows: list[dict], total_rows: list[dict]) -> list[dict]:
    workbook_candidates = candidates[:15]
    week_tabs = []
    for week in period_weeks:
        label = f"WK{week.get('week_number') or week.get('week_index')}"
        week_rows = build_week_sheet_rows(label, workbook_candidates, payroll_rows, week)
        week_tabs.append(
            {
                "label": label,
                "kind": "week",
                "columns": WEEK_SHEET_COLUMNS,
                "rows": week_rows,
                "summary": summarize_week_rows(week_rows),
            }
        )
    aggregated_totals = aggregate_week_sheet_totals(week_tabs)
    period_rows = build_period_sheet_rows(workbook_candidates, payroll_rows)
    payslip_rows = build_payslip_sheet_rows(period_rows, aggregated_totals)
    return [
        *week_tabs,
        {"label": "Periode", "kind": "period", "columns": PERIOD_SHEET_COLUMNS, "rows": period_rows},
        {"label": "Loonstrook", "kind": "payslip", "columns": PAYSLIP_SHEET_COLUMNS, "rows": payslip_rows},
    ]


def build_week_sheet_rows(sheet_label: str, candidates: list[dict], payroll_rows: list[dict], week: dict) -> list[dict]:
    rows = []
    week_index = int(week.get("week_index") or 1)
    for index, candidate in enumerate(candidates, start=1):
        payroll_row = next((row for row in payroll_rows if _key(row.get("employee_name")) == _key(candidate.get("name"))), {})
        weekly_hours = payroll_row.get("week_hours", [])
        worked_hours = _decimal(weekly_hours[week_index - 1] if len(weekly_hours) >= week_index else "")
        if not worked_hours:
            worked_hours = Decimal("32") + Decimal((index + week_index) % 4)
        worked_days = Decimal("5") if worked_hours >= 32 else Decimal("4")
        single_trip_km = Decimal(10 + ((index + week_index) % 18))
        total_km = single_trip_km * worked_days * 2
        net_advance = Decimal("0") if index % 4 else Decimal("150")
        rows.append(
            {
                "employee_name": candidate.get("name") or "-",
                "relation_id": candidate.get("id"),
                "contract_hours": "40",
                "worked_days": _format_number(worked_days),
                "worked_hours": _format_number(worked_hours),
                "vacation_hours": "0",
                "sickness_hours": "0",
                "rv_hours": "0",
                "kv_hours": "0",
                "holiday_hours": "0",
                "net_amount": _format_money(worked_hours * Decimal("13.75")),
                "commute_km": _format_number(total_km),
                "work_km": "0",
                "total_km": _format_number(total_km),
                "fuel_amount": _format_money(Decimal("0")),
                "extra_reimbursement": _format_money(Decimal("0")),
                "net_advance": _format_money(net_advance),
                "remarks": f"Dummyregel {sheet_label}",
                "project_info": "Voorbeeldproject",
                "single_trip_km": _format_number(single_trip_km),
                "hours_check": "dummy",
                "km_check": "dummy",
                "source": "echte kandidaat + dummy weekdata",
            }
        )
    return rows


def aggregate_week_sheet_totals(week_tabs: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for tab in week_tabs:
        for row in tab.get("rows", []):
            key = _key(row.get("employee_name"))
            if not key:
                continue
            item = totals.setdefault(
                key,
                {
                    "employee_name": row.get("employee_name"),
                    "total_worked_days": Decimal("0"),
                    "total_worked_hours": Decimal("0"),
                    "total_vacation_hours": Decimal("0"),
                    "total_sickness_hours": Decimal("0"),
                    "total_rv_hours": Decimal("0"),
                    "total_kv_hours": Decimal("0"),
                    "total_holiday_hours": Decimal("0"),
                    "total_km": Decimal("0"),
                    "total_declarations": Decimal("0"),
                    "total_net_advance": Decimal("0"),
                },
            )
            item["total_worked_days"] += _decimal(row.get("worked_days"))
            item["total_worked_hours"] += _decimal(row.get("worked_hours"))
            item["total_vacation_hours"] += _decimal(row.get("vacation_hours"))
            item["total_sickness_hours"] += _decimal(row.get("sickness_hours"))
            item["total_rv_hours"] += _decimal(row.get("rv_hours"))
            item["total_kv_hours"] += _decimal(row.get("kv_hours"))
            item["total_holiday_hours"] += _decimal(row.get("holiday_hours"))
            item["total_km"] += _decimal(row.get("total_km"))
            item["total_declarations"] += _decimal(row.get("extra_reimbursement"))
            item["total_net_advance"] += _decimal(row.get("net_advance"))
    return [
        {
            **item,
            "total_worked_days": _format_number(item["total_worked_days"]),
            "total_worked_hours": _format_number(item["total_worked_hours"]),
            "total_vacation_hours": _format_number(item["total_vacation_hours"]),
            "total_sickness_hours": _format_number(item["total_sickness_hours"]),
            "total_rv_hours": _format_number(item["total_rv_hours"]),
            "total_kv_hours": _format_number(item["total_kv_hours"]),
            "total_holiday_hours": _format_number(item["total_holiday_hours"]),
            "total_km": _format_number(item["total_km"]),
            "total_declarations": _format_money(item["total_declarations"]),
            "total_net_advance": _format_money(item["total_net_advance"]),
        }
        for item in totals.values()
    ]


def summarize_week_rows(rows: list[dict]) -> dict:
    return {
        "employees": len(rows),
        "hours": _format_number(sum((_decimal(row.get("worked_hours")) for row in rows), Decimal("0"))),
        "days": _format_number(sum((_decimal(row.get("worked_days")) for row in rows), Decimal("0"))),
        "km": _format_number(sum((_decimal(row.get("total_km")) for row in rows), Decimal("0"))),
    }


def summarize_workbook_tabs(tabs: list[dict]) -> dict:
    week_tabs = [tab for tab in tabs if tab.get("kind") == "week"]
    employee_names = {
        row.get("employee_name")
        for tab in week_tabs
        for row in tab.get("rows", [])
        if row.get("employee_name")
    }
    return {
        "employees": len(employee_names),
        "bookings": sum(len(tab.get("rows", [])) for tab in week_tabs),
        "days": _format_number(sum((_decimal(row.get("worked_days")) for tab in week_tabs for row in tab.get("rows", [])), Decimal("0"))),
        "hours": _format_number(sum((_decimal(row.get("worked_hours")) for tab in week_tabs for row in tab.get("rows", [])), Decimal("0"))),
    }


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
        cao_name = payroll_row.get("cao_name") or ("UTA" if index % 3 == 0 else "SAVG" if index % 2 == 0 else "Bouw & Infra")
        phase = "Fase B" if index % 2 else "Fase A"
        reservation_percent = Decimal("18.5") if cao_name.lower().startswith("bouw") else Decimal("16.0")
        bruto_total = hourly_wage * contract_hours
        staffing_factor = Decimal("1.83") if cao_name.lower().startswith("bouw") else Decimal("1.72")
        rows.append(
            {
                "employee_name": candidate.get("name") or "-",
                "relation_id": candidate.get("id"),
                "license_plate": _dummy_license_plate(index),
                "choice_budget": _format_money(Decimal("1100") + Decimal(index * 62)),
                "phase": phase,
                "pension_scheme": "StiPP Basis" if phase == "A" else "StiPP Plus",
                "contract_hours": _format_number(contract_hours),
                "cao_name": cao_name,
                "days_right": "20",
                "configuration": "B.02.1 Aannemingschaal 2" if cao_name == "SAVG" else "T4.2 F/G A",
                "function_name": candidate.get("notes") or "Medewerker bouw",
                "gross_hourly_wage": _format_money(hourly_wage),
                "gross_total": _format_money(bruto_total),
                "reservations": f"{_format_number(reservation_percent)}%",
                "bik": "0,00",
                "wage_component": "0,00",
                "reserve_vacation_days": "25",
                "reserve_adv": "20",
                "reserve_holiday": "5",
                "tsf": "0",
                "holiday_allowance": "8,33%",
                "rv_flex": "3,65%",
                "compensation_uta_days": "0",
                "compensation_adv_days": "0",
                "compensation_t": "0",
                "pension_component": "2,38%",
                "labor_cost_margin": _format_money(bruto_total * Decimal("0.18")),
                "staffing_factor": _format_number(staffing_factor),
                "net_period_basis": _format_money(bruto_total * Decimal("0.62")),
                "period_basis": "4 weken",
                "reservation_basis": f"{cao_name} concept",
                "source": "echte kandidaat + dummy looninstellingen",
                "status": "dummy",
                "excel_control": "zichtbaar gemaakt",
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
        pension_deduction = gross_reference * Decimal("0.035")
        payroll_tax = gross_reference * Decimal("0.29")
        net_reference = (gross_reference * Decimal("0.62")) + travel_allowance + declarations
        net_to_receive = max(net_reference - net_advance, Decimal("0"))
        rows.append(
            {
                "employee_name": period_row.get("employee_name"),
                "relation_id": period_row.get("relation_id"),
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
                "gross_wage": _format_money(gross_reference),
                "pension_deduction": _format_money(pension_deduction),
                "payroll_tax": _format_money(payroll_tax),
                "net_after_deductions": _format_money(max(gross_reference - pension_deduction - payroll_tax, Decimal("0"))),
                "gv": "0,00",
                "vkr": "0,00",
                "ik": "0,00",
                "net_total": _format_money(net_to_receive),
                "car_license_plate": period_row.get("license_plate"),
                "weekly_wage": _format_money(gross_reference / Decimal("4") if gross_reference else Decimal("0")),
                "ntf_sl": _format_money(Decimal("0")),
                "bkp_ntfsl": _format_money(Decimal("0")),
                "sickness_value": _format_money(Decimal("0")),
                "personnel_costs": _format_money(gross_reference * Decimal("1.35")),
                "notes": "Dummy/concept, nog valideren",
                "status": "concept",
                "excel_control": "zichtbaar gemaakt",
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
