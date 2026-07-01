from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


WEEK_SHEET_COLUMNS = [
    {"label": "Werknemer", "key": "employee_name"},
    {"label": "Urenbriefje", "key": "timesheet_link"},
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
    {"label": "Betaling", "key": "payment_action"},
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
    {"label": "Uurtarief", "key": "hourly_wage"},
    {"label": "Tarief bron", "key": "hourly_wage_source"},
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

PAYMENT_SHEET_COLUMNS = [
    {"label": "Week", "key": "week_label"},
    {"label": "Werknemer", "key": "employee_name"},
    {"label": "Urenbriefje", "key": "timesheet_link"},
    {"label": "Uren", "key": "worked_hours"},
    {"label": "Km", "key": "total_km"},
    {"label": "Netto bedrag", "key": "net_amount"},
    {"label": "Project", "key": "project_info"},
    {"label": "Actie", "key": "payment_action"},
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
    workbook_candidates = candidates[:15] if payroll_rows else []
    week_tabs = []
    payment_source_tabs = []
    for week in period_weeks:
        label = f"WK{week.get('week_number') or week.get('week_index')}"
        all_week_rows = build_week_sheet_rows(label, workbook_candidates, payroll_rows, week)
        week_rows = [
            row for row in all_week_rows
            if row.get("payroll_status") == "loon_berekenen"
        ]
        payment_source_tabs.append({"label": label, "rows": all_week_rows})
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
    payable_rows = build_payment_sheet_rows(payment_source_tabs, "uit_te_betalen")
    paid_rows = build_payment_sheet_rows(payment_source_tabs, "uitbetaald")
    return [
        *week_tabs,
        {"label": "Periode", "kind": "period", "columns": PERIOD_SHEET_COLUMNS, "rows": period_rows},
        {"label": "Loonstrook", "kind": "payslip", "columns": PAYSLIP_SHEET_COLUMNS, "rows": payslip_rows},
        {"label": "Uit te betalen", "kind": "payment", "columns": PAYMENT_SHEET_COLUMNS, "rows": payable_rows},
        {"label": "Uitbetaald", "kind": "paid", "columns": PAYMENT_SHEET_COLUMNS, "rows": paid_rows},
    ]


def build_week_sheet_rows(sheet_label: str, candidates: list[dict], payroll_rows: list[dict], week: dict) -> list[dict]:
    rows = []
    if not payroll_rows:
        return rows
    week_index = int(week.get("week_index") or 1)
    candidates_by_name = {_key(candidate.get("name")): candidate for candidate in candidates}
    for index, payroll_row in enumerate(payroll_rows, start=1):
        employee_name = payroll_row.get("employee_name") or "-"
        candidate = candidates_by_name.get(_key(employee_name), {})
        weekly_hours = payroll_row.get("week_hours", [])
        worked_hours = _decimal(weekly_hours[week_index - 1] if len(weekly_hours) >= week_index else "")
        if not worked_hours:
            continue
        weekly_days = payroll_row.get("week_worked_days", [])
        weekly_km = payroll_row.get("week_total_km", [])
        week_timesheet_ids = payroll_row.get("week_timesheet_ids", [])
        timesheet_ids = week_timesheet_ids[week_index - 1] if len(week_timesheet_ids) >= week_index else []
        timesheet_label = "Open" if len(timesheet_ids) <= 1 else f"Open ({len(timesheet_ids)})"
        weekly_statuses = payroll_row.get("week_statuses", [])
        payroll_statuses = weekly_statuses[week_index - 1] if len(weekly_statuses) >= week_index else []
        payroll_status = _payment_status(payroll_statuses)
        weekly_blockers = payroll_row.get("week_blockers", [])
        payroll_blockers = weekly_blockers[week_index - 1] if len(weekly_blockers) >= week_index else []
        payroll_blocker_items = [str(blocker).strip() for blocker in payroll_blockers if str(blocker).strip()]
        payroll_blocker_message = " ".join(payroll_blocker_items)
        worked_days = _decimal(weekly_days[week_index - 1] if len(weekly_days) >= week_index else "") or _decimal(payroll_row.get("worked_days") or payroll_row.get("days_worked"))
        single_trip_km = _decimal(payroll_row.get("single_trip_km"))
        work_km = _decimal(payroll_row.get("work_km"))
        total_km = _decimal(weekly_km[week_index - 1] if len(weekly_km) >= week_index else "") or _decimal(payroll_row.get("total_km")) or ((single_trip_km * worked_days * 2) + work_km if single_trip_km and worked_days else Decimal("0"))
        net_advance = _decimal(payroll_row.get("net_advance"))
        rows.append(
            {
                "employee_name": employee_name,
                "timesheet_id": timesheet_ids[0] if timesheet_ids else "",
                "timesheet_ids": ",".join(str(timesheet_id) for timesheet_id in timesheet_ids if timesheet_id),
                "timesheet_link": timesheet_label if timesheet_ids else "-",
                "relation_id": payroll_row.get("relation_id") or candidate.get("id"),
                "contract_hours": payroll_row.get("standard_week_hours") or payroll_row.get("payroll_cao_hours") or "",
                "worked_days": _format_number(worked_days) if worked_days else "",
                "worked_hours": _format_number(worked_hours),
                "vacation_hours": payroll_row.get("vacation_hours") or "",
                "sickness_hours": payroll_row.get("sickness_hours") or "",
                "rv_hours": payroll_row.get("rv_hours") or "",
                "kv_hours": payroll_row.get("kv_hours") or "",
                "holiday_hours": payroll_row.get("holiday_hours") or "",
                "net_amount": payroll_row.get("net_amount") or "",
                "commute_km": _format_number(total_km) if total_km else "",
                "work_km": _format_number(work_km) if work_km else "",
                "total_km": _format_number(total_km) if total_km else "",
                "fuel_amount": payroll_row.get("fuel_amount") or "",
                "extra_reimbursement": payroll_row.get("extra_reimbursement") or "",
                "net_advance": _format_money(net_advance) if net_advance else "",
                "remarks": payroll_row.get("remarks") or payroll_row.get("notes") or "",
                "project_info": payroll_row.get("projects") or "",
                "single_trip_km": _format_number(single_trip_km) if single_trip_km else "",
                "hours_check": "urenverwerking",
                "km_check": "urenverwerking",
                "source": "urenverwerking",
                "payroll_status": payroll_status,
                "payroll_status_label": _payment_status_label(payroll_status),
                "payment_action": _payment_action_label(payroll_status),
                "payroll_blocker_items": payroll_blocker_items,
                "payroll_blocker_message": payroll_blocker_message,
            }
        )
    return rows


def _payment_status(statuses) -> str:
    normalized = {
        str(status or "").strip().lower().replace(" ", "_")
        for status in (statuses or [])
        if str(status or "").strip()
    }
    if "uitbetaald" in normalized:
        return "uitbetaald"
    if "uit_te_betalen" in normalized:
        return "uit_te_betalen"
    return "loon_berekenen"


def _payment_status_label(status: str) -> str:
    return {
        "uit_te_betalen": "Uit te betalen",
        "uitbetaald": "Uitbetaald",
    }.get(status, "Loon berekenen")


def _payment_action_label(status: str) -> str:
    if status == "uit_te_betalen":
        return "Uitbetaald"
    if status == "uitbetaald":
        return "Afgerond"
    return "Uitbetalen"


def build_payment_sheet_rows(week_tabs: list[dict], target_status: str) -> list[dict]:
    rows = []
    for tab in week_tabs:
        for row in tab.get("rows", []):
            if row.get("payroll_status") != target_status:
                continue
            payment_row = {
                "week_label": tab.get("label") or "",
                "employee_name": row.get("employee_name") or "",
                "timesheet_id": row.get("timesheet_id") or "",
                "timesheet_ids": row.get("timesheet_ids") or "",
                "timesheet_link": row.get("timesheet_link") or "-",
                "relation_id": row.get("relation_id") or "",
                "worked_hours": row.get("worked_hours") or "",
                "total_km": row.get("total_km") or "",
                "net_amount": row.get("net_amount") or "",
                "project_info": row.get("project_info") or "",
                "payroll_status": row.get("payroll_status") or "",
                "payroll_status_label": row.get("payroll_status_label") or "",
                "payment_action": row.get("payment_action") or "",
                "payroll_blocker_items": row.get("payroll_blocker_items") or [],
                "payroll_blocker_message": row.get("payroll_blocker_message") or "",
            }
            rows.append(payment_row)
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
    if not payroll_rows:
        return []
    payroll_by_name = {
        _key(row.get("employee_name")): row
        for row in payroll_rows
        if row.get("employee_name")
    }
    candidates_by_name = {_key(candidate.get("name")): candidate for candidate in candidates}
    rows = []
    for index, payroll_row in enumerate(payroll_rows, start=1):
        employee_name = payroll_row.get("employee_name") or "-"
        candidate = candidates_by_name.get(_key(employee_name), {})
        payroll_hourly_wage = _decimal(payroll_row.get("payroll_hourly_wage"))
        if payroll_hourly_wage:
            hourly_wage = payroll_hourly_wage
            hourly_wage_source = "Medewerkerkaart"
        else:
            hourly_wage = _decimal(payroll_row.get("hourly_wage"))
            hourly_wage_source = payroll_row.get("hourly_wage_source") or ("CAO" if hourly_wage else "")
        contract_hours = _decimal(payroll_row.get("payroll_cao_hours")) or _decimal(payroll_row.get("standard_week_hours"))
        cao_name = payroll_row.get("cao_name") or payroll_row.get("payroll_cao_name") or ""
        phase = payroll_row.get("payroll_phase") or ""
        bruto_total = hourly_wage * contract_hours if hourly_wage and contract_hours else Decimal("0")
        rows.append(
            {
                "employee_name": employee_name,
                "relation_id": payroll_row.get("relation_id") or candidate.get("id"),
                "license_plate": payroll_row.get("payroll_license_plate") or "",
                "choice_budget": payroll_row.get("payroll_choice_budget") or "",
                "phase": phase,
                "pension_scheme": payroll_row.get("payroll_pension") or "",
                "contract_hours": _format_number(contract_hours) if contract_hours else "",
                "cao_name": cao_name,
                "days_right": payroll_row.get("payroll_days_right") or "",
                "configuration": payroll_row.get("payroll_scale") or "",
                "function_name": payroll_row.get("payroll_function") or "",
                "gross_hourly_wage": _format_money(hourly_wage) if hourly_wage else "",
                "hourly_wage_source": hourly_wage_source,
                "gross_total": _format_money(bruto_total) if bruto_total else "",
                "reservations": payroll_row.get("reservations") or "",
                "bik": payroll_row.get("bik") or "",
                "wage_component": payroll_row.get("wage_component") or "",
                "reserve_vacation_days": payroll_row.get("reserve_vacation_days") or "",
                "reserve_adv": payroll_row.get("reserve_adv") or "",
                "reserve_holiday": payroll_row.get("reserve_holiday") or "",
                "tsf": payroll_row.get("tsf") or "",
                "holiday_allowance": payroll_row.get("holiday_allowance") or "",
                "rv_flex": payroll_row.get("rv_flex") or "",
                "compensation_uta_days": payroll_row.get("compensation_uta_days") or "",
                "compensation_adv_days": payroll_row.get("compensation_adv_days") or "",
                "compensation_t": payroll_row.get("compensation_t") or "",
                "pension_component": payroll_row.get("pension_component") or "",
                "labor_cost_margin": payroll_row.get("labor_cost_margin") or "",
                "staffing_factor": payroll_row.get("staffing_factor") or "",
                "net_period_basis": payroll_row.get("net_period_basis") or "",
                "period_basis": payroll_row.get("period_basis") or "",
                "reservation_basis": payroll_row.get("reservation_basis") or "",
                "source": "urenverwerking",
                "status": payroll_row.get("status") or "",
                "excel_control": "",
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
                "hourly_wage": _format_money(hourly_wage) if hourly_wage else "",
                "hourly_wage_source": period_row.get("hourly_wage_source") or "",
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
                "notes": period_row.get("notes") or "",
                "status": period_row.get("status") or "",
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
    text = str(value or "0").replace("€", "").replace(" ", "").strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
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
    return f"€ {value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}".replace(".", ",")
