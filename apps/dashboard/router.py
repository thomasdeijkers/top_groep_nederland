from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from apps.dashboard.auth import auth_enabled
from apps.dashboard.placeholders import (
    ACTIVITY_ITEMS,
    MODULES,
    IMPORT_STEPS,
    REVIEW_ITEMS,
    TICKET_QUEUES,
)
from apps.dashboard.organizations import create_organization, list_organizations
from apps.dashboard.openai_usage import get_openai_usage_summary, list_openai_api_audit_events
from apps.dashboard.payroll_excel import build_payroll_output_workbook
from apps.dashboard.records import (
    archive_payroll_period,
    create_cao_setting,
    create_manual_timesheet,
    create_project,
    create_payroll_period,
    create_payroll_period_batch,
    create_payroll_parameter_version,
    create_payroll_running_balance_mutation,
    clear_payroll_test_workspace,
    delete_payroll_period,
    finalize_payroll_period_for_payment,
    get_cao_setting,
    get_payroll_parameter_version,
    get_payroll_period,
    get_timesheet_payroll_lock,
    get_project,
    get_overview_data,
    get_payroll_period_defaults,
    get_relation_payroll_context,
    get_timesheet_channel_tiles,
    ensure_relation_for_candidate_match,
    list_audit_events,
    list_cao_settings,
    list_projects,
    list_payroll_periods,
    list_payroll_year_overview,
    list_payroll_datamodel_status,
    get_payroll_data_diagnostics,
    list_payroll_running_balances,
    list_payroll_employee_arrangements,
    list_payroll_parameters,
    list_candidates,
    list_project_options,
    list_principals,
    list_relations,
    list_relation_statuses,
    list_relation_status_counts,
    list_relation_tab_counts,
    list_tickets,
    list_vacancies,
    list_vacancy_status_counts,
    list_vacancy_statuses,
    list_whatsapp_timesheets,
    log_audit_event,
    reopen_payroll_period_for_editing,
    save_payroll_workbook_cell,
    search_candidate_matches,
    update_cao_setting,
    update_payroll_employee_arrangement,
    update_payroll_running_balance_account,
)
from apps.dashboard.relations import (
    create_candidate,
    create_principal,
    create_relation,
    archive_relation,
    delete_candidate,
    delete_principal,
    delete_vacancy,
    get_candidate,
    get_principal,
    get_relation,
    get_vacancy,
    create_vacancy,
    save_relation_photo,
    update_candidate,
    update_principal,
    update_relation,
    update_vacancy,
)
from apps.dashboard.stats import get_dashboard_stats, get_database_status, get_empty_dashboard_stats, get_health, get_server_overview
from apps.dashboard.timesheet_corrections import TimesheetValidationError, save_field_corrections, send_to_payroll, validate_timesheet
from apps.dashboard.timesheet_uploads import import_complete_period_timesheets, reparse_timesheet_upload, save_timesheet_upload
from apps.dashboard.whatsapp_actions import archive_whatsapp_timesheet, delete_whatsapp_timesheet
from jobs.imports.otys_export import import_otys_organizations, parse_otys_csv
from jobs.imports.table_import import import_candidates, import_principals, import_vacancies, parse_csv

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")


def _relations_url(tab: str = "candidates", edit: int | None = None, q: str = "", status: str = "", anchor: str = "") -> str:
    params = {"tab": tab}
    if edit is not None:
        params["edit"] = edit
    if q:
        params["q"] = q
    if status:
        params["status"] = status
    return f"/dashboard/relations?{urlencode(params)}{anchor}"


def _audit(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    label: str = "",
    description: str = "",
    status: str = "",
    metadata: dict | None = None,
) -> None:
    log_audit_event(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=label,
        description=description,
        status=status,
        metadata=metadata,
        actor_name="Admin",
    )


def _db_error_detail(exc: Exception) -> str:
    diag = getattr(exc, "diag", None)
    table_name = getattr(diag, "table_name", "") if diag else ""
    constraint_name = getattr(diag, "constraint_name", "") if diag else ""
    pgerror = str(getattr(exc, "pgerror", "") or "").strip()
    parts = [part for part in (table_name, constraint_name, pgerror or str(exc)) if part]
    return " | ".join(parts)


def _audit_changed_fields(corrections: dict) -> str:
    labels = {
        "employee_name": "naam werknemer",
        "employee_phone": "telefoon werknemer",
        "project_number": "projectnummer",
        "work_name": "project",
        "principal_name": "opdrachtgever",
        "week_number": "weeknummer",
        "total_hours": "totaal uren",
        "absence_code": "verzuimcode",
        "remarks": "opmerking",
    }
    changed = []
    for key, value in corrections.items():
        if str(value or "").strip():
            changed.append(labels.get(key, key.replace("_", " ")))
    if not changed:
        return "Geen ingevulde velden gewijzigd."
    shown = changed[:6]
    suffix = f" en {len(changed) - len(shown)} extra velden" if len(changed) > len(shown) else ""
    return f"Aangepast: {', '.join(shown)}{suffix}."


def _split_candidate_name(name: str) -> tuple[str, str]:
    parts = str(name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _context_value(active_page: str, label: str, fallback, loader):
    try:
        return loader()
    except Exception as exc:
        print(f"DASHBOARD_CONTEXT_SECTION_ERROR {active_page}.{label}: {type(exc).__name__}: {exc}")
        return fallback() if callable(fallback) else fallback


def _audit_relation_fields(data: dict) -> str:
    labels = {
        "name": "bedrijfsnaam",
        "first_name": "voornaam",
        "last_name": "achternaam",
        "contact_name": "contactpersoon",
        "email": "e-mail",
        "phone": "telefoon",
        "status": "status",
        "city": "plaats",
        "street": "straat",
        "postal_code": "postcode",
        "country": "land",
        "kvk_number": "KvK",
        "vat_number": "BTW",
        "payroll_license_plate": "kenteken",
        "payroll_choice_budget": "keuzebudget",
        "payroll_phase": "fase",
        "payroll_pension": "pensioen",
        "payroll_cao_hours": "uren CAO",
        "payroll_days_right": "recht op dagen",
        "payroll_scale": "inregeling",
        "payroll_function": "functie",
        "payroll_hourly_wage": "bruto uurloon",
        "notes": "notitie",
    }
    changed = [label for key, label in labels.items() if str(data.get(key) or "").strip()]
    if not changed:
        return "Relatiekaart opgeslagen zonder extra ingevulde velden."
    shown = changed[:6]
    suffix = f" en {len(changed) - len(shown)} extra velden" if len(changed) > len(shown) else ""
    return f"Relatiekaart bijgewerkt. Aangepast/ingevuld: {', '.join(shown)}{suffix}."


def _timesheet_stage(status: str) -> str:
    normalized = (status or "").strip().lower().replace(" ", "_")
    if normalized in {"doorgestuurd_naar_loonadministratie", "verwerkt", "processed", "definitief_loonbetaling"}:
        return "archief"
    if normalized in {"goed_te_keuren", "approval", "akkoord_nodig"}:
        return "valideren"
    if normalized in {"loon_te_berekenen", "loon_berekenen", "loon"}:
        return "loon"
    return "controle"


def _timesheet_workflow_tabs(items: list[dict], active_stage: str) -> list[dict]:
    labels = {
        "all": ("Alle taken", "Alle open urenbriefjes"),
        "controle": ("Controle", "Ingekomen urenstaten openen en corrigeren"),
        "valideren": ("Valideren", "Gecontroleerde uren boeken op opdrachtgever en project"),
        "loon": ("Loon berekenen", "Gevalideerde uren klaarzetten voor loonberekening"),
        "archief": ("Archief", "Definitief gevalideerde urenbriefjes"),
    }
    return [
        {
            "key": key,
            "label": label,
            "description": description,
            "count": len(items) if key == "all" else sum(1 for item in items if item.get("workflow_stage") == key),
            "active": key == active_stage,
        }
        for key, (label, description) in labels.items()
    ]


def _timesheet_payroll_period_shortcut(items: list[dict], periods: list[dict]) -> dict:
    fallback = {
        "url": "/dashboard/periods#periodes",
        "title": "Open",
        "description": "Laatste controle en accorderen in loonperiodes.",
        "matched": False,
    }
    if not items or not periods:
        return fallback
    eligible_items = [item for item in items if item.get("workflow_stage") == "loon"] or items
    period_hits: dict[int, dict] = {}
    for item in eligible_items:
        work_date = item.get("work_date") or (item.get("received_at").date() if item.get("received_at") else None)
        if not work_date:
            continue
        for period in periods:
            start_date = period.get("raw_start_date")
            end_date = period.get("raw_end_date")
            if start_date and end_date and start_date <= work_date <= end_date:
                hit = period_hits.setdefault(period["id"], {"period": period, "count": 0})
                hit["count"] += 1
                break
    if not period_hits:
        return fallback
    best = sorted(
        period_hits.values(),
        key=lambda item: (item["count"], item["period"].get("raw_start_date") or ""),
        reverse=True,
    )[0]
    period = best["period"]
    return {
        "url": f"/dashboard/periods?period={period['id']}#periode-verloning",
        "title": period.get("name") or f"Periode {period.get('period_number')}",
        "description": f"Open loonverwerking voor {best['count']} taak/taken in deze periode.",
        "matched": True,
    }


def _attach_timesheet_payroll_period_link(item: dict, periods: list[dict]) -> None:
    period = _matching_payroll_period_for_timesheet(item, periods)
    if not period:
        item["payroll_period_url"] = ""
        item["payroll_period_title"] = ""
        return
    item["payroll_period_url"] = f"/dashboard/periods?period={period['id']}#periode-verloning"
    item["payroll_period_title"] = period.get("name") or f"Periode {period.get('period_number')}"


def _timesheet_locked_response(timesheet_id: int, request: Request | None = None):
    lock = get_timesheet_payroll_lock(timesheet_id)
    if not lock.get("locked"):
        return None
    message = "Dit urenbriefje is gevalideerd voor loonbetaling en staat op slot. Zet de loonperiode terug om weer te wijzigen."
    if request and request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": False, "locked": True, "error": message}, status_code=423)
    query = urlencode({"tab": "task", "stage": "archief", "timesheet": timesheet_id, "locked": "1"})
    return RedirectResponse(f"/dashboard/timesheets?{query}#digital-timesheet", status_code=303)


def _matching_payroll_period_for_timesheet(item: dict, periods: list[dict]) -> dict | None:
    work_date = item.get("work_date") or (item.get("received_at").date() if item.get("received_at") else None)
    if not work_date:
        return None
    for period in periods:
        start_date = period.get("raw_start_date")
        end_date = period.get("raw_end_date")
        if start_date and end_date and start_date <= work_date <= end_date:
            return period
    return None


def _filter_timesheets(items: list[dict], query: str, workflow_stage: str) -> list[dict]:
    filtered = items if workflow_stage == "all" else [item for item in items if item.get("workflow_stage") == workflow_stage]
    search = (query or "").strip().lower()
    if not search:
        return filtered

    def haystack(item: dict) -> str:
        return " ".join(
            str(value or "")
            for value in (
                item.get("sender_name"),
                item.get("sender_phone"),
                item.get("employee_name"),
                item.get("media_filename"),
                item.get("matched_name"),
                item.get("workflow_stage_label"),
                item.get("source_channel_label"),
                item.get("status"),
            )
        ).lower()

    return [item for item in filtered if search in haystack(item)]


def _dashboard_context(
    active_page: str,
    edit_id: int | None = None,
    query: str = "",
    timesheet_id: int | None = None,
    workflow_stage: str = "all",
    timesheet_tab: str = "overview",
    relation_tab: str = "candidates",
    status_filter: str = "",
    show_relation_form: bool = False,
    project_id: int | None = None,
    period_id: int | None = None,
    cao_id: int | None = None,
    parameter_version_id: int | None = None,
    show_cao_form: bool = False,
):
    data_page = "timesheets" if active_page in {"timesheets", "whatsapp"} else "relations" if active_page in {"relations", "candidates", "principals"} else active_page
    if active_page == "server":
        stats = get_empty_dashboard_stats()
        server_overview = get_server_overview()
        return {
            "active_page": active_page,
            "auth_enabled": auth_enabled(),
            "stats": stats["cards"],
            "database": server_overview["database"],
            "modules": MODULES,
            "review_items": REVIEW_ITEMS,
            "activity_items": ACTIVITY_ITEMS,
            "audit_events": [],
            "server_metrics": server_overview["server_metrics"],
            "server_system_tiles": server_overview["server_system_tiles"],
            "server_scheduler_tiles": server_overview["server_scheduler_tiles"],
            "server_otys_tiles": server_overview["server_otys_tiles"],
            "scheduled_jobs": server_overview["scheduled_jobs"],
            "ticket_queues": TICKET_QUEUES,
            "directory_results": [],
            "relations": [],
            "import_steps": IMPORT_STEPS,
            "whatsapp_inbox": [],
            "selected_timesheet": None,
            "timesheet_stage": "all",
            "timesheet_stage_items": [],
            "timesheet_workflow_tabs": [],
            "timesheet_tab": "overview",
            "relation_tab": "candidates",
            "show_relation_form": False,
            "candidate_relations": [],
            "timesheet_candidate_options": [],
            "principal_relations": [],
            "status_tiles": [],
            "relation_tab_counts": {"candidates": 0, "principals": 0},
            "candidates": [],
            "tickets": [],
            "vacancies": [],
            "selected_relation": None,
            "selected_relation_payroll": None,
            "selected_vacancy": None,
            "query": query,
            "overview_data": {
                "counts": {
                    "candidates": 0,
                    "principals": 0,
                    "vacancies": 0,
                    "whatsapp_timesheet_inbox": 0,
                },
                "recent": [],
                "whatsapp_workflow": [],
            },
            "openai_usage": {"month_cost_usd": 0, "month_requests": 0, "month_tokens": 0, "requests": 0, "total_tokens": 0},
            "principal_options": [],
            "project_options": [],
            "projects": [],
            "selected_project": None,
            "selected_payroll_period": None,
            "payroll_periods": [],
            "archived_payroll_periods": [],
            "payroll_year_overview": [],
            "payroll_datamodel_status": [],
            "payroll_data_diagnostics": [],
            "payroll_period_defaults": {},
            "payroll_parameters": [],
            "selected_payroll_parameter_version": None,
            "payroll_employee_arrangements": [],
            "payroll_running_balances": [],
            "cao_settings": [],
            "selected_cao_setting": None,
            "show_cao_form": False,
            "timesheet_channel_tiles": [],
            "country_options": [
                "Nederland",
                "Belgie",
                "Duitsland",
                "Polen",
                "Roemenie",
                "Bulgarije",
                "Portugal",
                "Spanje",
                "Italie",
                "Frankrijk",
                "Overig",
            ],
        }

    stats = _context_value(data_page, "stats", get_empty_dashboard_stats(), lambda: get_dashboard_stats()) if data_page == "overview" else get_empty_dashboard_stats()
    database_status = stats["database"] if data_page == "overview" else _context_value(data_page, "database_status", {"status": "unavailable", "meta": "Database status niet beschikbaar"}, get_database_status)
    server_overview = {
        "server_metrics": [],
        "server_system_tiles": [],
        "server_scheduler_tiles": [],
        "server_otys_tiles": [],
        "scheduled_jobs": [],
    }
    organizations = _context_value(data_page, "organizations", [], list_organizations) if data_page == "overview" else []
    active_status = status_filter if data_page in {"relations", "vacancies"} else ""
    relations = _context_value(data_page, "relations", [], lambda: list_relations(query=query, status=active_status)) if data_page == "relations" else []
    candidate_relations = _context_value(data_page, "candidate_relations", [], lambda: list_relations(query=query, relation_type="candidate", status=active_status)) if data_page == "relations" else []
    timesheet_candidate_options = _context_value(data_page, "timesheet_candidate_options", [], lambda: list_relations(limit=200, relation_type="candidate")) if data_page == "timesheets" else []
    principal_relations = _context_value(data_page, "principal_relations", [], lambda: list_relations(query=query, relation_type="principal", status=active_status)) if data_page == "relations" else []
    principal_limit = 500 if data_page == "timesheets" else 100
    principals = _context_value(data_page, "principal_options", [], lambda: list_principals(limit=principal_limit, query=query if data_page == "relations" else "")) if data_page in {"relations", "vacancies", "projects", "timesheets"} else []
    imported_candidates = _context_value(data_page, "imported_candidates", [], lambda: list_candidates(query=query)) if data_page == "relations" else []
    imported_tickets = _context_value(data_page, "tickets", [], list_tickets) if data_page == "tickets" else []
    imported_vacancies = _context_value(data_page, "vacancies", [], lambda: list_vacancies(query=query, status=active_status)) if data_page == "vacancies" else []
    relation_status_options = _context_value(data_page, "relation_status_options", [], lambda: list_relation_statuses("candidate" if relation_tab == "candidates" else "principal")) if data_page == "relations" else []
    vacancy_status_options = _context_value(data_page, "vacancy_status_options", [], list_vacancy_statuses) if data_page == "vacancies" else []
    relation_tab_counts = _context_value(data_page, "relation_tab_counts", {"candidates": 0, "principals": 0}, list_relation_tab_counts) if data_page == "relations" else {"candidates": 0, "principals": 0}
    status_tiles = (
        _context_value(data_page, "vacancy_status_counts", [], lambda: list_vacancy_status_counts(query if data_page == "vacancies" else ""))
        if data_page == "vacancies"
        else _context_value(data_page, "relation_status_counts", [], lambda: list_relation_status_counts("candidate" if relation_tab == "candidates" else "principal", query if data_page == "relations" else ""))
        if data_page == "relations"
        else []
    )
    whatsapp_timesheets = _context_value(data_page, "whatsapp_timesheets", [], list_whatsapp_timesheets) if data_page == "timesheets" else []
    overview_data = _context_value(data_page, "overview_data", {
        "counts": {
            "candidates": 0,
            "principals": 0,
            "vacancies": 0,
            "tickets": 0,
            "whatsapp_timesheet_inbox": 0,
        },
        "recent": [],
        "whatsapp_workflow": [],
        "weekly_hours_yoy": [],
    }, get_overview_data) if data_page == "overview" else {
        "counts": {
            "candidates": 0,
            "principals": 0,
            "vacancies": 0,
            "tickets": 0,
            "whatsapp_timesheet_inbox": 0,
        },
        "recent": [],
        "whatsapp_workflow": [],
        "weekly_hours_yoy": [],
    }
    audit_events = _context_value(data_page, "audit_events", [], lambda: list_audit_events(160 if data_page == "audit" else 8)) if data_page in {"overview", "audit", "settings", "periods"} else []
    audit_menu_groups = _audit_menu_groups(audit_events) if data_page == "audit" else []
    openai_api_audit_events = _context_value(data_page, "openai_api_audit_events", [], lambda: list_openai_api_audit_events(40)) if data_page == "audit" else []
    openai_usage = _context_value(data_page, "openai_usage", {"month_cost_usd": 0, "month_requests": 0, "month_tokens": 0, "requests": 0, "total_tokens": 0}, get_openai_usage_summary)
    project_options = _context_value(data_page, "project_options", [], list_project_options) if data_page in {"timesheets", "projects", "periods"} else []
    projects = _context_value(data_page, "projects", [], lambda: list_projects(query=query)) if data_page == "projects" else []
    selected_project = _context_value(data_page, "selected_project", None, lambda: get_project(project_id)) if data_page == "projects" and project_id else None
    payroll_periods = _context_value(data_page, "payroll_periods", [], list_payroll_periods) if data_page in {"periods", "timesheets"} else []
    archived_payroll_periods = _context_value(data_page, "archived_payroll_periods", [], lambda: list_payroll_periods(archived=True)) if data_page in {"periods", "timesheets"} else []
    payroll_year_overview = _context_value(data_page, "payroll_year_overview", [], list_payroll_year_overview) if data_page == "periods" else []
    payroll_datamodel_status = _context_value(data_page, "payroll_datamodel_status", [], lambda: list_payroll_datamodel_status(limit=40)) if data_page == "periods" else []
    payroll_data_diagnostics = _context_value(data_page, "payroll_data_diagnostics", [], get_payroll_data_diagnostics) if data_page == "periods" else []
    payroll_period_defaults = _context_value(data_page, "payroll_period_defaults", {}, get_payroll_period_defaults) if data_page == "periods" else {}
    selected_payroll_period = _context_value(data_page, "selected_payroll_period", None, lambda: get_payroll_period(period_id)) if data_page == "periods" and period_id else None
    payroll_parameters = _context_value(data_page, "payroll_parameters", [], list_payroll_parameters) if data_page == "settings" else []
    selected_payroll_parameter_version = _context_value(data_page, "selected_payroll_parameter_version", None, lambda: get_payroll_parameter_version(parameter_version_id)) if data_page == "settings" and parameter_version_id else None
    payroll_employee_arrangements = _context_value(data_page, "payroll_employee_arrangements", [], list_payroll_employee_arrangements) if data_page == "settings" else []
    payroll_running_balances = _context_value(data_page, "payroll_running_balances", [], list_payroll_running_balances) if data_page == "settings" else []
    cao_settings = _context_value(data_page, "cao_settings", [], list_cao_settings) if data_page in {"settings", "periods"} else []
    selected_cao_setting = _context_value(data_page, "selected_cao_setting", None, lambda: get_cao_setting(cao_id)) if data_page == "settings" and cao_id else None
    selected_relation = _context_value(data_page, "selected_relation", None, lambda: get_relation(edit_id)) if data_page == "relations" and edit_id else None
    selected_relation_payroll = None
    if selected_relation and selected_relation.get("relation_type") == "candidate":
        selected_relation_payroll = _context_value(data_page, "selected_relation_payroll", None, lambda: get_relation_payroll_context(selected_relation.get("id")))
    selected_relation_audit_events = []
    if selected_relation:
        relation_audit_types = {"relatie", "candidate", "principal", selected_relation.get("relation_type") or ""}
        relation_id_text = str(selected_relation.get("id"))
        selected_relation_audit_events = [
            item
            for item in _context_value(data_page, "selected_relation_audit_events", [], lambda: list_audit_events(200))
            if (
                item.get("entity_id") == selected_relation.get("id")
                and item.get("entity_type") in relation_audit_types
            )
            or str((item.get("metadata") or {}).get("relation_id") or "") == relation_id_text
        ][:40]
    selected_vacancy = _context_value(data_page, "selected_vacancy", None, lambda: get_vacancy(edit_id)) if data_page == "vacancies" and edit_id else None
    relation_tab = relation_tab if relation_tab in {"candidates", "principals"} else "candidates"
    show_relation_form = show_relation_form or bool(selected_relation)

    timesheet_payroll_periods = payroll_periods + archived_payroll_periods
    whatsapp_inbox = whatsapp_timesheets
    for item in whatsapp_inbox:
        try:
            item.setdefault("parsed_map", {
                field.get("key") or field.get("label") or f"field_{index}": field
                for index, field in enumerate(item.get("parsed_fields", []))
            })
            item["workflow_stage"] = _timesheet_stage(item.get("status", ""))
            item["workflow_stage_label"] = {
                "controle": "Te controleren",
                "valideren": "Te valideren",
                "loon": "Loon berekenen",
                "archief": "Archief",
            }.get(item["workflow_stage"], "Te controleren")
            _attach_timesheet_payroll_period_link(item, timesheet_payroll_periods)
            item["payroll_locked"] = item["workflow_stage"] == "archief"
        except Exception as exc:
            print(f"DASHBOARD_CONTEXT_SECTION_ERROR {data_page}.timesheet_row: {type(exc).__name__}: {exc}")
            item.setdefault("parsed_map", {})
            item["workflow_stage"] = "controle"
            item["workflow_stage_label"] = "Te controleren"

    workflow_stage = workflow_stage if workflow_stage in {"all", "controle", "valideren", "loon", "archief"} else "all"
    timesheet_tab = timesheet_tab if timesheet_tab in {"overview", "task"} else "overview"
    timesheet_stage_items = _filter_timesheets(whatsapp_inbox, query, workflow_stage)
    timesheet_payroll_period_shortcut = _timesheet_payroll_period_shortcut(timesheet_stage_items, timesheet_payroll_periods)
    selected_timesheet = next((item for item in whatsapp_inbox if item["id"] == timesheet_id), None) if timesheet_id else None
    if timesheet_tab == "task" and not selected_timesheet:
        timesheet_tab = "overview"

    return {
        "active_page": active_page,
        "auth_enabled": auth_enabled(),
        "stats": stats["cards"],
        "database": database_status,
        "modules": MODULES,
        "review_items": REVIEW_ITEMS,
        "activity_items": ACTIVITY_ITEMS,
        "audit_events": audit_events,
        "audit_menu_groups": audit_menu_groups,
        "openai_api_audit_events": openai_api_audit_events,
        "server_metrics": server_overview["server_metrics"],
        "server_system_tiles": server_overview["server_system_tiles"],
        "server_scheduler_tiles": server_overview["server_scheduler_tiles"],
        "server_otys_tiles": server_overview["server_otys_tiles"],
        "scheduled_jobs": server_overview["scheduled_jobs"],
        "ticket_queues": TICKET_QUEUES,
        "directory_results": relations or principals or organizations,
        "relations": relations,
        "status_filter": status_filter,
        "relation_status_options": relation_status_options,
        "vacancy_status_options": vacancy_status_options,
        "status_tiles": status_tiles,
        "relation_tab_counts": relation_tab_counts,
        "import_steps": IMPORT_STEPS,
        "whatsapp_inbox": whatsapp_inbox,
        "selected_timesheet": selected_timesheet,
        "timesheet_stage": workflow_stage,
        "timesheet_stage_items": timesheet_stage_items,
        "timesheet_workflow_tabs": _timesheet_workflow_tabs(whatsapp_inbox, workflow_stage),
        "timesheet_payroll_period_shortcut": timesheet_payroll_period_shortcut,
        "timesheet_tab": timesheet_tab,
        "relation_tab": relation_tab,
        "show_relation_form": show_relation_form,
        "candidate_relations": candidate_relations,
        "timesheet_candidate_options": timesheet_candidate_options,
        "principal_relations": principal_relations,
        "candidates": imported_candidates,
        "tickets": imported_tickets,
        "vacancies": imported_vacancies,
        "selected_relation": selected_relation,
        "selected_relation_payroll": selected_relation_payroll,
        "selected_relation_audit_events": selected_relation_audit_events,
        "selected_vacancy": selected_vacancy,
        "query": query,
        "overview_data": overview_data,
        "openai_usage": openai_usage,
        "principal_options": principals,
        "project_options": project_options,
        "projects": projects,
        "selected_project": selected_project,
        "selected_payroll_period": selected_payroll_period,
        "payroll_periods": payroll_periods,
        "archived_payroll_periods": archived_payroll_periods,
        "payroll_year_overview": payroll_year_overview,
        "payroll_datamodel_status": payroll_datamodel_status,
        "payroll_data_diagnostics": payroll_data_diagnostics,
        "payroll_period_defaults": payroll_period_defaults,
        "payroll_parameters": payroll_parameters,
        "selected_payroll_parameter_version": selected_payroll_parameter_version,
        "payroll_employee_arrangements": payroll_employee_arrangements,
        "payroll_running_balances": payroll_running_balances,
        "cao_settings": cao_settings,
        "selected_cao_setting": selected_cao_setting,
        "show_cao_form": show_cao_form or bool(selected_cao_setting),
        "timesheet_channel_tiles": _context_value(data_page, "timesheet_channel_tiles", [], get_timesheet_channel_tiles) if data_page == "timesheets" else [],
        "country_options": [
            "Nederland",
            "Belgie",
            "Duitsland",
            "Polen",
            "Roemenie",
            "Bulgarije",
            "Portugal",
            "Spanje",
            "Italie",
            "Frankrijk",
            "Overig",
        ],
    }


def _audit_menu_groups(events: list[dict]) -> list[dict]:
    labels = [
        "Urenverwerking",
        "Controle",
        "Loon berekenen",
        "Accorderen",
        "Periodes",
        "Relaties",
        "Vacatures",
        "Projecten",
        "Instellingen",
        "Archief",
        "Verwijderd",
        "Systeem",
    ]
    grouped = {label: [] for label in labels}
    other = []
    for event in events:
        label = event.get("status") or event.get("entity_type") or "Overig"
        target = label if label in grouped else None
        if not target and str(label).lower() in {"akkoord"}:
            target = "Accorderen"
        if target:
            grouped[target].append(event)
        else:
            other.append(event)
    result = [{"label": label, "items": grouped[label]} for label in labels if grouped[label]]
    if other:
        result.append({"label": "Overig", "items": other})
    return result


def _render_dashboard(
    request: Request,
    active_page: str,
    edit_id: int | None = None,
    query: str = "",
    timesheet_id: int | None = None,
    workflow_stage: str = "all",
    timesheet_tab: str = "overview",
    relation_tab: str = "candidates",
    status_filter: str = "",
    show_relation_form: bool = False,
    project_id: int | None = None,
    period_id: int | None = None,
    cao_id: int | None = None,
    parameter_version_id: int | None = None,
    show_cao_form: bool = False,
):
    try:
        context = _dashboard_context(active_page, edit_id, query, timesheet_id, workflow_stage, timesheet_tab, relation_tab, status_filter, show_relation_form, project_id, period_id, cao_id, parameter_version_id, show_cao_form)
    except Exception as exc:
        print(f"DASHBOARD_CONTEXT_ERROR {active_page}: {type(exc).__name__}: {exc}")
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="nl">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Dashboard tijdelijk niet geladen</title>
                <style>
                    body { margin: 0; font-family: Arial, sans-serif; background: #0d171d; color: #f4f7f8; }
                    main { max-width: 760px; margin: 12vh auto; padding: 32px; background: #1d282f; border: 1px solid #3b4a52; border-radius: 8px; }
                    h1 { margin: 0 0 12px; font-size: 28px; }
                    p { color: #c8d6dd; line-height: 1.5; }
                    a { color: #99f0bf; font-weight: 700; }
                </style>
            </head>
            <body>
                <main>
                    <h1>Dashboard tijdelijk niet geladen</h1>
                    <p>De app is bereikbaar, maar het dashboard kon de data niet volledig laden. De fout is in de serverlog gezet zodat we hem gericht kunnen oplossen.</p>
                    <p><a href="/dashboard">Opnieuw proberen</a></p>
                </main>
            </body>
            </html>
            """,
            status_code=200,
        )
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context,
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return _render_dashboard(request, "overview")


@router.get("/dashboard/candidates", response_class=HTMLResponse)
def candidates_page(request: Request, edit: int | None = None, q: str = "", status: str = ""):
    return RedirectResponse(_relations_url("candidates", edit, q, status), status_code=303)


@router.get("/dashboard/principals", response_class=HTMLResponse)
def principals_page(request: Request, edit: int | None = None, q: str = "", status: str = ""):
    return RedirectResponse(_relations_url("principals", edit, q, status), status_code=303)


@router.get("/dashboard/relations", response_class=HTMLResponse)
def relations_page(request: Request, edit: int | None = None, q: str = "", tab: str = "candidates", status: str = "", new: bool = Query(False)):
    return _render_dashboard(request, "relations", edit, q, relation_tab=tab, status_filter=status, show_relation_form=new)


@router.get("/dashboard/relations/photo/{relation_id}")
def relation_photo(relation_id: int):
    relation = get_relation(relation_id)
    if relation and relation.get("photo_path"):
        return FileResponse(relation["photo_path"])
    return RedirectResponse("/dashboard/static/top-groep-nederland.png", status_code=303)


@router.get("/dashboard/vacancies", response_class=HTMLResponse)
def vacancies_page(request: Request, edit: int | None = None, q: str = "", status: str = ""):
    return _render_dashboard(request, "vacancies", edit, q, status_filter=status)


@router.get("/dashboard/projects", response_class=HTMLResponse)
def projects_page(request: Request, q: str = "", project: int | None = None):
    return _render_dashboard(request, "projects", query=q, project_id=project)


@router.get("/dashboard/periods", response_class=HTMLResponse)
def periods_page(request: Request, period: int | None = None):
    return _render_dashboard(request, "periods", period_id=period)


@router.get("/dashboard/tickets", response_class=HTMLResponse)
def tickets_page(request: Request):
    return _render_dashboard(request, "tickets")


@router.get("/dashboard/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    return _render_dashboard(request, "audit")


@router.get("/dashboard/whatsapp", response_class=HTMLResponse)
def whatsapp_page(request: Request):
    return RedirectResponse("/dashboard/timesheets", status_code=303)


@router.get("/dashboard/timesheets", response_class=HTMLResponse)
def timesheets_page(request: Request, stage: str = "all", timesheet: int | None = None, tab: str = "overview", q: str = ""):
    return _render_dashboard(request, "timesheets", query=q, timesheet_id=timesheet, workflow_stage=stage, timesheet_tab=tab)


@router.get("/dashboard/whatsapp/document/{timesheet_id}")
def whatsapp_document(timesheet_id: int):
    for item in list_whatsapp_timesheets(limit=100):
        if item["id"] == timesheet_id and item.get("media_path"):
            return FileResponse(item["media_path"])
    return RedirectResponse("/dashboard/timesheets", status_code=303)


@router.get("/dashboard/timesheets/document/{timesheet_id}")
def timesheet_document(timesheet_id: int):
    return whatsapp_document(timesheet_id)


@router.post("/api/whatsapp/timesheet-upload")
async def upload_whatsapp_timesheet(
    file: UploadFile = File(...),
    sender_name: str = Form(""),
    sender_phone: str = Form(""),
):
    try:
        content = await file.read()
        record_id = save_timesheet_upload(
            content=content,
            filename=file.filename or "urenbriefje.jpg",
            sender_name=sender_name,
            sender_phone=sender_phone,
            source_channel="manual_upload",
            allow_openai=True,
        )
        _audit("Urenbriefje geupload", "urenbriefje", record_id, file.filename or "urenbriefje.jpg", "Nieuw urenbriefje ontvangen en klaargezet voor controle.", "Urenverwerking")
        return RedirectResponse(f"/dashboard/timesheets?tab=overview&stage=all&uploaded={record_id}#timesheet-inbox", status_code=303)
    except Exception as exc:
        print(f"TIMESHEET_UPLOAD_ERROR {type(exc).__name__}: {_db_error_detail(exc)}")
        query = urlencode({"tab": "overview", "stage": "all", "upload_error": type(exc).__name__})
        return RedirectResponse(f"/dashboard/timesheets?{query}#timesheet-inbox", status_code=303)


@router.get("/api/whatsapp/complete-period-import")
def import_complete_period_timesheet_set_get():
    return RedirectResponse("/dashboard/timesheets?tab=overview&stage=all#timesheet-inbox", status_code=303)


@router.post("/api/whatsapp/complete-period-import")
async def import_complete_period_timesheet_set(
    files: list[UploadFile] = File(...),
    replace_existing: bool = Form(True),
    allow_openai: bool = Form(False),
):
    try:
        uploads = [(file.filename or "urenbriefje.zip", await file.read()) for file in files]
        result = import_complete_period_timesheets(uploads, replace_existing=replace_existing, allow_openai=allow_openai)
        _audit(
            "Complete loonperiode geimporteerd",
            "urenbriefje",
            None,
            "Complete loonperiode",
            f"{result['imported']} urenbriefjes geimporteerd; {result['replaced']} oude testtaken vervangen.",
            "Urenverwerking",
            metadata={
                "source_channel": "complete_payroll_period_import",
                "imported": result["imported"],
                "replaced": result["replaced"],
                "skipped": len(result["skipped"]),
            },
        )
        return RedirectResponse(
            f"/dashboard/timesheets?tab=overview&stage=all&complete_imported={result['imported']}&complete_replaced={result['replaced']}&complete_skipped={len(result['skipped'])}#timesheet-inbox",
            status_code=303,
        )
    except Exception as exc:
        print(f"COMPLETE_PERIOD_IMPORT_ERROR {type(exc).__name__}: {_db_error_detail(exc)}")
        query = urlencode({"tab": "overview", "stage": "all", "import_error": type(exc).__name__})
        return RedirectResponse(f"/dashboard/timesheets?{query}#timesheet-inbox", status_code=303)


@router.post("/api/test/payroll-workspace/clear")
def clear_payroll_workspace_for_testing(return_to: str = Form("timesheets")):
    result = clear_payroll_test_workspace()
    query = (
        f"cleared_timesheets={result['deleted_timesheets']}"
        f"&cleared_payroll_rows={result['deleted_payroll_rows']}"
    )
    target = (
        f"/dashboard/periods?{query}#periodes"
        if return_to == "periods"
        else f"/dashboard/timesheets?tab=overview&stage=all&{query}#timesheet-inbox"
    )
    return RedirectResponse(
        target,
        status_code=303,
    )


@router.post("/api/whatsapp/timesheet/{timesheet_id}/corrections")
async def correct_whatsapp_timesheet(timesheet_id: int, request: Request):
    locked_response = _timesheet_locked_response(timesheet_id, request)
    if locked_response:
        return locked_response
    form = await request.form()
    corrections = {
        key.removeprefix("field_"): value
        for key, value in form.items()
        if key.startswith("field_")
    }
    manual_parse = str(form.get("manual_parse") or "").strip() == "1"
    matched_relation_raw = str(form.get("matched_relation_id") or "").strip()
    matched_relation_id = ensure_relation_for_candidate_match(matched_relation_raw)
    clear_candidate_match = "matched_relation_id" in form and not matched_relation_raw
    save_field_corrections(
        timesheet_id,
        corrections,
        matched_relation_id=matched_relation_id,
        clear_candidate_match=clear_candidate_match,
    )
    description = _audit_changed_fields(corrections)
    if matched_relation_id:
        description += f" Kandidaatkaart #{matched_relation_id} gekoppeld."
    if manual_parse:
        description = f"Handmatig uit het urenbriefje overgenomen. {description}".strip()
    _audit(
        "Urenbriefje handmatig geparsed" if manual_parse else "Urenbriefje gecorrigeerd",
        "urenbriefje",
        timesheet_id,
        f"Urenbriefje {timesheet_id}",
        description,
        "Controle",
    )
    if request.headers.get("X-Requested-With") == "fetch":
        return JSONResponse({"ok": True, "timesheet_id": timesheet_id})
    return RedirectResponse(f"/dashboard/timesheets?stage=valideren&timesheet={timesheet_id}", status_code=303)


@router.get("/api/candidates/search")
def search_candidates(q: str = "", limit: int = Query(40, ge=1, le=80)):
    return {"results": search_candidate_matches(q, limit)}


@router.post("/api/whatsapp/timesheet/{timesheet_id}/candidate")
def create_candidate_from_timesheet(
    timesheet_id: int,
    candidate_name: str = Form(""),
    phone: str = Form(""),
    city: str = Form(""),
    email: str = Form(""),
):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    first_name, last_name = _split_candidate_name(candidate_name)
    record_id = create_candidate(
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "city": city,
            "status": "Nieuw",
            "source": "Urenbriefje",
            "notes": f"Aangemaakt vanuit urenbriefje {timesheet_id}.",
        }
    )
    save_field_corrections(
        timesheet_id,
        {
            "employee_name": candidate_name,
            "employee_phone": phone,
        },
        matched_relation_id=record_id,
    )
    _audit("Kandidaat aangemaakt", "candidate", record_id, candidate_name or "Kandidaat", f"Aangemaakt en gekoppeld vanuit urenbriefje {timesheet_id}.", "Relaties")
    return RedirectResponse(f"/dashboard/timesheets?tab=task&stage=valideren&timesheet={timesheet_id}&candidate_created={record_id}#digital-timesheet", status_code=303)


@router.get("/api/principals/search")
def search_principals(q: str = "", limit: int = Query(120, ge=1, le=500)):
    return {"results": list_principals(limit=limit, query=q)}


@router.post("/api/whatsapp/timesheet/{timesheet_id}/reparse")
def reparse_whatsapp_timesheet(timesheet_id: int):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    reparse_timesheet_upload(timesheet_id, allow_openai=True)
    _audit("Urenbriefje met OCR en OpenAI geparsed", "urenbriefje", timesheet_id, f"Urenbriefje {timesheet_id}", "OCR/OpenAI parsing opnieuw uitgevoerd voor alle weekstaatvelden.", "Controle")
    return RedirectResponse(f"/dashboard/timesheets?tab=task&stage=controle&timesheet={timesheet_id}#digital-timesheet", status_code=303)


@router.post("/api/whatsapp/timesheet/{timesheet_id}/validate")
def validate_whatsapp_timesheet(
    timesheet_id: int,
    matched_relation_id: str = Form(""),
    principal_id: int | None = Form(None),
    project_id: int | None = Form(None),
):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    try:
        selected_candidate_id = ensure_relation_for_candidate_match(matched_relation_id)
        if selected_candidate_id:
            save_field_corrections(timesheet_id, {}, matched_relation_id=selected_candidate_id)
        validate_timesheet(timesheet_id, principal_id, project_id)
    except TimesheetValidationError as exc:
        query = urlencode({"tab": "task", "stage": "valideren", "timesheet": timesheet_id, "validate_error": str(exc)})
        return RedirectResponse(f"/dashboard/timesheets?{query}#digital-timesheet", status_code=303)
    _audit("Urenbriefje gevalideerd", "urenbriefje", timesheet_id, f"Urenbriefje {timesheet_id}", "Uren zijn gekoppeld aan kandidaat, opdrachtgever en project.", "Loon berekenen")
    return RedirectResponse(f"/dashboard/timesheets?stage=loon&timesheet={timesheet_id}", status_code=303)


@router.post("/api/whatsapp/timesheet/{timesheet_id}/payroll")
def payroll_whatsapp_timesheet(timesheet_id: int):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    send_to_payroll(timesheet_id)
    _audit("Doorgestuurd naar loonadministratie", "urenbriefje", timesheet_id, f"Urenbriefje {timesheet_id}", "Urenbriefje is doorgestuurd voor loonadministratie.", "Accorderen")
    return RedirectResponse("/dashboard/periods#periodes", status_code=303)


@router.post("/api/whatsapp/timesheet/{timesheet_id}/archive")
def archive_whatsapp_message(timesheet_id: int):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    archive_whatsapp_timesheet(timesheet_id)
    _audit("Urenbriefje gearchiveerd", "urenbriefje", timesheet_id, f"Urenbriefje {timesheet_id}", "Urenbriefje is uit de actieve werklijst gehaald.", "Archief")
    return RedirectResponse("/dashboard/timesheets", status_code=303)


@router.post("/api/whatsapp/timesheet/{timesheet_id}/delete")
def delete_whatsapp_message(timesheet_id: int):
    locked_response = _timesheet_locked_response(timesheet_id)
    if locked_response:
        return locked_response
    delete_whatsapp_timesheet(timesheet_id)
    _audit("Urenbriefje verwijderd", "urenbriefje", timesheet_id, f"Urenbriefje {timesheet_id}", "Urenbriefje is verwijderd uit de actieve verwerking.", "Verwijderd")
    return RedirectResponse("/dashboard/timesheets", status_code=303)


@router.post("/api/payroll/employee-arrangements/{arrangement_id}")
async def save_payroll_employee_arrangement(arrangement_id: int, request: Request):
    form = await request.form()
    description = update_payroll_employee_arrangement(arrangement_id, dict(form))
    _audit(
        "Medewerker-inrichting aangepast",
        "payroll_employee_arrangement",
        arrangement_id,
        f"Medewerker-inrichting {arrangement_id}",
        description,
        "Verloning",
    )
    return RedirectResponse("/dashboard/settings#medewerker-inrichting", status_code=303)


@router.post("/api/payroll/running-balances/{account_id}")
async def save_payroll_running_balance(account_id: int, request: Request):
    form = await request.form()
    description = update_payroll_running_balance_account(account_id, dict(form))
    _audit(
        "Lopend saldo aangepast",
        "payroll_running_balance",
        account_id,
        f"Lopend saldo {account_id}",
        description,
        "Verloning",
    )
    return RedirectResponse("/dashboard/settings#lopende-saldi", status_code=303)


@router.post("/api/payroll/running-balances/{account_id}/mutations")
async def add_payroll_running_balance_mutation(account_id: int, request: Request):
    form = await request.form()
    description = create_payroll_running_balance_mutation(account_id, dict(form))
    _audit(
        "Saldo-mutatie geboekt",
        "payroll_running_balance",
        account_id,
        f"Lopend saldo {account_id}",
        description,
        "Verloning",
    )
    return RedirectResponse("/dashboard/settings#lopende-saldi", status_code=303)


@router.post("/api/timesheets/manual")
def create_manual_timesheet_entry(
    relation_id: str = Form(""),
    employee_name: str = Form(""),
    sender_phone: str = Form(""),
    work_date: str = Form(""),
    hours: str = Form(""),
    principal_id: str = Form(""),
    principal_name: str = Form(""),
    project_id: str = Form(""),
    project_name: str = Form(""),
    status: str = Form("controle"),
    remarks: str = Form(""),
):
    timesheet_id = create_manual_timesheet(locals())
    stage = _timesheet_stage(status)
    return RedirectResponse(f"/dashboard/timesheets?stage={stage}&timesheet={timesheet_id}", status_code=303)


@router.get("/dashboard/server", response_class=HTMLResponse)
def server_page(request: Request):
    return _render_dashboard(request, "server")


@router.get("/dashboard/settings", response_class=HTMLResponse)
def settings_page(request: Request, cao: str = "", parameter_version: str = ""):
    cao_id = int(cao) if cao.isdigit() else None
    parameter_version_id = int(parameter_version) if parameter_version.isdigit() else None
    return _render_dashboard(request, "settings", cao_id=cao_id, parameter_version_id=parameter_version_id, show_cao_form=cao == "new")


@router.post("/api/settings/cao")
def save_cao_setting(
    name: str = Form(""),
    version_label: str = Form(""),
    effective_from: str = Form(""),
    effective_until: str = Form(""),
    standard_week_hours: str = Form(""),
    overtime_after_hours: str = Form(""),
    weekday_overtime_percent: str = Form(""),
    saturday_percent: str = Form(""),
    sunday_percent: str = Form(""),
    holiday_percent: str = Form(""),
    travel_cost_per_km: str = Form(""),
    default_hourly_wage: str = Form(""),
    status: str = Form("concept"),
    notes: str = Form(""),
):
    setting_id = create_cao_setting(locals())
    _audit("CAO aangemaakt", "cao", setting_id, name or "CAO instelling", "Nieuwe CAO-regelset aangemaakt voor verloning.", "Instellingen")
    return RedirectResponse(f"/dashboard/settings?cao={setting_id}#cao-instellingen", status_code=303)


@router.post("/api/settings/cao/{setting_id}")
def edit_cao_setting(
    setting_id: int,
    name: str = Form(""),
    version_label: str = Form(""),
    effective_from: str = Form(""),
    effective_until: str = Form(""),
    standard_week_hours: str = Form(""),
    overtime_after_hours: str = Form(""),
    weekday_overtime_percent: str = Form(""),
    saturday_percent: str = Form(""),
    sunday_percent: str = Form(""),
    holiday_percent: str = Form(""),
    travel_cost_per_km: str = Form(""),
    default_hourly_wage: str = Form(""),
    status: str = Form("concept"),
    notes: str = Form(""),
):
    update_cao_setting(setting_id, locals())
    _audit("CAO bijgewerkt", "cao", setting_id, name or "CAO instelling", "CAO-regelset bijgewerkt voor toekomstige berekeningen.", "Instellingen")
    return RedirectResponse(f"/dashboard/settings?cao={setting_id}#cao-instellingen", status_code=303)


@router.post("/api/settings/payroll-parameters")
def save_payroll_parameter_version(
    parameter_version_id: str = Form(""),
    parameter_id: str = Form(""),
    parameter_key: str = Form(""),
    name: str = Form(""),
    category: str = Form("grondslag"),
    unit: str = Form("decimal"),
    value_type: str = Form("decimal"),
    applies_to: str = Form("both"),
    description: str = Form(""),
    source_reference: str = Form(""),
    year: str = Form(""),
    period_number: str = Form(""),
    effective_from: str = Form(""),
    effective_until: str = Form(""),
    build_value: str = Form(""),
    uta_value: str = Form(""),
    text_value: str = Form(""),
    version_source_reference: str = Form(""),
    notes: str = Form(""),
    version_status: str = Form("active"),
):
    version_id = create_payroll_parameter_version(locals())
    version = get_payroll_parameter_version(version_id) or {}
    label = version.get("name") or name or parameter_key or f"parameter {parameter_id}"
    period_label = f"{version.get('year') or year} / P{version.get('period_number') or period_number}"
    action = "Grondslag parameter bijgewerkt" if parameter_version_id else "Grondslag parameter opgeslagen"
    _audit(
        action,
        "payroll_parameter_version",
        version_id,
        label,
        f"Parameter-versie voor {period_label} opgeslagen met bron en toelichting.",
        "Instellingen",
        metadata={
            "parameter_id": version.get("parameter_id") or parameter_id,
            "parameter_key": version.get("parameter_key") or parameter_key,
            "year": version.get("year") or year,
            "period_number": version.get("period_number") or period_number,
            "effective_from": version.get("effective_from_input") or effective_from,
            "build_value": version.get("build_value_input") or build_value,
            "uta_value": version.get("uta_value_input") or uta_value,
            "source_reference": version.get("source_reference") or version_source_reference,
        },
    )
    return RedirectResponse(f"/dashboard/settings?parameter_version={version_id}#grondslag-parameters", status_code=303)


@router.get("/api/health")
def health():
    return get_health()


@router.get("/api/stats")
def stats():
    return get_dashboard_stats()


@router.post("/api/customers")
def create_customer(
    organization_type: str = Form(...),
    name: str = Form(...),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    city: str = Form(""),
):
    create_organization(
        organization_type=organization_type,
        name=name,
        email=email,
        phone=phone,
        website=website,
        city=city,
    )
    return RedirectResponse("/dashboard?created=1#relaties", status_code=303)


@router.post("/api/projects")
def save_project(
    title: str = Form(""),
    reference_number: str = Form(""),
    relation_name: str = Form(""),
    location: str = Form(""),
    status: str = Form("Actief"),
    payroll_cao_setting_id: str = Form(""),
    notes: str = Form(""),
):
    project_id = create_project(locals())
    _audit("Project aangemaakt", "project", project_id, title or "Project", "Nieuw project aangemaakt en beschikbaar gemaakt voor urenboeking.", "Projecten")
    return RedirectResponse(f"/dashboard/projects?created={project_id}#projecten", status_code=303)


@router.post("/api/periods")
def save_payroll_period(
    year: str = Form(""),
    period_number: str = Form(""),
    name: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    status: str = Form("concept"),
    notes: str = Form(""),
    period_count: str = Form("1"),
    display_period_number: str = Form(""),
):
    if name or end_date:
        period_id = create_payroll_period(locals())
        created_ids = [period_id]
    else:
        created_ids = create_payroll_period_batch(locals())
        period_id = created_ids[-1] if created_ids else 0
    _audit("Periode aangemaakt", "periode", period_id, name or f"Periode {period_number}", f"{len(created_ids)} vierwekelijkse loonperiode(s) aangemaakt of bijgewerkt.", "Periodes")
    return RedirectResponse(f"/dashboard/periods?created={period_id}#periodes", status_code=303)


@router.get("/api/periods/{period_id}/excel/export")
def export_payroll_period_excel(period_id: int):
    period = get_payroll_period(period_id)
    if not period:
        return RedirectResponse("/dashboard/periods#periodes", status_code=303)
    output_path = Path("runtime/exports/payroll") / f"periode-{period_id}-verloning.xlsx"
    try:
        build_payroll_output_workbook(output_path, period, use_tgn_template=True)
    except Exception as exc:
        fallback_period = {
            **period,
            "workbook_tabs": [
                {
                    "label": "Export",
                    "columns": [{"label": "Melding", "key": "message"}],
                    "rows": [{"message": f"Export kon niet volledig worden opgebouwd: {type(exc).__name__}"}],
                }
            ],
        }
        build_payroll_output_workbook(output_path, fallback_period)
    filename = _safe_download_filename(period.get("name", f"Periode {period_id}"))
    _audit(
        "Excel verloning geexporteerd",
        "periode",
        period_id,
        period.get("name", f"Periode {period_id}"),
        "Excel-output gemaakt in TGN-templateopzet met weektabs, Periode, Loonstrook en Grondslag.",
        "export",
    )
    return FileResponse(
        output_path,
        filename=f"{filename}-verloning.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _safe_download_filename(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in (" ", "-", "_") else "-" for character in value)
    safe = " ".join(safe.split()).strip(" -_")
    return safe or "periode"


@router.post("/api/periods/{period_id}/workbook-cell")
async def save_payroll_period_workbook_cell(period_id: int, request: Request):
    payload = await request.json()
    result = save_payroll_workbook_cell(period_id, payload)
    status_code = 200 if result.get("ok") else 423 if result.get("locked") else 400
    return JSONResponse(result, status_code=status_code)


@router.post("/api/periods/{period_id}/archive")
def archive_period(period_id: int):
    archive_payroll_period(period_id, archived=True)
    _audit("Periode gearchiveerd", "periode", period_id, f"Periode {period_id}", "Loonperiode verplaatst naar het archief.", "Periodes")
    return RedirectResponse("/dashboard/periods#periode-archief", status_code=303)


@router.post("/api/periods/{period_id}/approve")
def approve_period(period_id: int):
    period = get_payroll_period(period_id)
    phase_status = (period or {}).get("payroll_phase_status") or {}
    exception_summary = (period or {}).get("payroll_exception_summary") or {}
    if not phase_status.get("can_approve"):
        _audit(
            "Loonperiode akkoord geblokkeerd",
            "periode",
            period_id,
            (period or {}).get("name") or f"Periode {period_id}",
            phase_status.get("detail") or "Loonperiode heeft nog blokkerende controlesignalen.",
            "Controle vereist",
            metadata={
                "blocking_exceptions": exception_summary.get("blocking", 0),
                "warning_exceptions": exception_summary.get("warning", 0),
                "phase_status": phase_status.get("label", "Controle vereist"),
            },
        )
        return RedirectResponse(f"/dashboard/periods?period={period_id}#periode-verloning", status_code=303)

    result = finalize_payroll_period_for_payment(period_id)
    _audit(
        "Loonperiode gevalideerd voor loonbetaling",
        "periode",
        period_id,
        (period or {}).get("name") or f"Periode {period_id}",
        f"Definitief gevalideerd voor salarisadministratie. {result['timesheets']} urenbriefjes en {result['bookings']} projectboekingen verwerkt. Payroll-controle: {phase_status.get('audit_summary', 'geen blokkades')}.",
        "Archief",
        metadata={
            "blocking_exceptions": exception_summary.get("blocking", 0),
            "warning_exceptions": exception_summary.get("warning", 0),
            "phase_status": phase_status.get("label", "Akkoord"),
            "processed_timesheets": result["timesheets"],
            "processed_bookings": result["bookings"],
            "processed_week_inputs": result["week_inputs"],
        },
    )
    return RedirectResponse("/dashboard/periods#periode-archief", status_code=303)


@router.post("/api/periods/{period_id}/restore")
def restore_period(period_id: int):
    result = reopen_payroll_period_for_editing(period_id)
    _audit(
        "Periode teruggezet",
        "periode",
        period_id,
        f"Periode {period_id}",
        f"Loonperiode teruggezet uit het archief; {result['timesheets']} urenbriefjes zijn weer bewerkbaar voor loonberekening.",
        "Periodes",
        metadata={
            "reopened_timesheets": result["timesheets"],
            "reopened_bookings": result["bookings"],
            "reopened_week_inputs": result["week_inputs"],
        },
    )
    return RedirectResponse("/dashboard/periods#periodes", status_code=303)


@router.post("/api/periods/{period_id}/delete")
def delete_period(period_id: int):
    delete_payroll_period(period_id)
    _audit("Periode definitief verwijderd", "periode", period_id, f"Periode {period_id}", "Loonperiode definitief verwijderd. Urenboekingen zijn niet verwijderd.", "Periodes")
    return RedirectResponse("/dashboard/periods#periodes", status_code=303)


async def _relation_photo_from_upload(photo: UploadFile | None):
    if not photo or not photo.filename:
        return None
    content = await photo.read()
    return save_relation_photo(content, photo.filename)


@router.post("/api/relations")
async def save_relation(
    relation_type: str = Form("candidate"),
    name: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    city: str = Form(""),
    status: str = Form("Actief"),
    source: str = Form(""),
    street: str = Form(""),
    house_number: str = Form(""),
    house_number_addition: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form("Nederland"),
    owner: str = Form(""),
    availability: str = Form(""),
    hourly_rate: str = Form(""),
    payroll_license_plate: str = Form(""),
    payroll_choice_budget: str = Form(""),
    payroll_phase: str = Form(""),
    payroll_pension: str = Form(""),
    payroll_cao_hours: str = Form(""),
    payroll_days_right: str = Form(""),
    payroll_scale: str = Form(""),
    payroll_function: str = Form(""),
    payroll_hourly_wage: str = Form(""),
    kvk_number: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile | None = File(None),
):
    photo_data = await _relation_photo_from_upload(photo)
    record_id = create_relation(locals(), photo_data)
    tab = "principals" if relation_type == "principal" else "candidates"
    label = name if relation_type == "principal" else " ".join(part for part in (first_name, last_name) if part).strip()
    _audit("Relatie aangemaakt", relation_type, record_id, label or "Relatie", "Nieuwe relatie aangemaakt in het dashboard.", "Relaties")
    return RedirectResponse(_relations_url(tab, edit=record_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/relations/{relation_id}")
async def edit_relation(
    relation_id: int,
    relation_type: str = Form("candidate"),
    name: str = Form(""),
    first_name: str = Form(""),
    last_name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    city: str = Form(""),
    status: str = Form("Actief"),
    source: str = Form(""),
    street: str = Form(""),
    house_number: str = Form(""),
    house_number_addition: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form("Nederland"),
    owner: str = Form(""),
    availability: str = Form(""),
    hourly_rate: str = Form(""),
    payroll_license_plate: str = Form(""),
    payroll_choice_budget: str = Form(""),
    payroll_phase: str = Form(""),
    payroll_pension: str = Form(""),
    payroll_cao_hours: str = Form(""),
    payroll_days_right: str = Form(""),
    payroll_scale: str = Form(""),
    payroll_function: str = Form(""),
    payroll_hourly_wage: str = Form(""),
    kvk_number: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile | None = File(None),
):
    photo_data = await _relation_photo_from_upload(photo)
    update_relation(relation_id, locals(), photo_data)
    tab = "principals" if relation_type == "principal" else "candidates"
    label = name if relation_type == "principal" else " ".join(part for part in (first_name, last_name) if part).strip()
    _audit("Relatie bijgewerkt", relation_type, relation_id, label or f"Relatie {relation_id}", _audit_relation_fields(locals()), "Relaties")
    return RedirectResponse(_relations_url(tab, edit=relation_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/relations/{relation_id}/delete")
def remove_relation(relation_id: int):
    archive_relation(relation_id)
    _audit("Relatie gearchiveerd", "relatie", relation_id, f"Relatie {relation_id}", "Relatie is gearchiveerd.", "Archief")
    return RedirectResponse(_relations_url(), status_code=303)


@router.post("/api/relations/{relation_id}/archive")
def archive_relation_record(relation_id: int):
    archive_relation(relation_id)
    _audit("Relatie gearchiveerd", "relatie", relation_id, f"Relatie {relation_id}", "Relatie is gearchiveerd.", "Archief")
    return RedirectResponse(_relations_url(), status_code=303)


@router.post("/api/candidates")
def save_candidate(
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    city: str = Form(""),
    status: str = Form(""),
    source: str = Form(""),
    address: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    owner: str = Form(""),
    availability: str = Form(""),
    hourly_rate: str = Form(""),
    notes: str = Form(""),
):
    record_id = create_candidate(locals())
    _audit("Kandidaat aangemaakt", "candidate", record_id, " ".join(part for part in (first_name, last_name) if part).strip() or "Kandidaat", "Nieuwe kandidaat aangemaakt.", "Relaties")
    return RedirectResponse(_relations_url("candidates", edit=record_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/candidates/{candidate_id}")
def edit_candidate(
    candidate_id: int,
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    city: str = Form(""),
    status: str = Form(""),
    source: str = Form(""),
    address: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    owner: str = Form(""),
    availability: str = Form(""),
    hourly_rate: str = Form(""),
    notes: str = Form(""),
):
    update_candidate(candidate_id, locals())
    _audit("Kandidaat bijgewerkt", "candidate", candidate_id, " ".join(part for part in (first_name, last_name) if part).strip() or "Kandidaat", "Kandidaatgegevens bijgewerkt.", "Relaties")
    return RedirectResponse(_relations_url("candidates", edit=candidate_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/candidates/{candidate_id}/delete")
def remove_candidate(candidate_id: int):
    delete_candidate(candidate_id)
    _audit("Kandidaat verwijderd", "candidate", candidate_id, f"Kandidaat {candidate_id}", "Kandidaat verwijderd uit de database.", "Verwijderd")
    return RedirectResponse(_relations_url("candidates", anchor="#relaties"), status_code=303)


@router.post("/api/principals")
def save_principal(
    name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    city: str = Form(""),
    status: str = Form(""),
    source: str = Form(""),
    address: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    kvk_number: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
):
    record_id = create_principal(locals())
    _audit("Opdrachtgever aangemaakt", "principal", record_id, name or "Opdrachtgever", "Nieuwe opdrachtgever aangemaakt.", "Relaties")
    return RedirectResponse(_relations_url("principals", edit=record_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/principals/{principal_id}")
def edit_principal(
    principal_id: int,
    name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    city: str = Form(""),
    status: str = Form(""),
    source: str = Form(""),
    address: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    kvk_number: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
):
    update_principal(principal_id, locals())
    _audit("Opdrachtgever bijgewerkt", "principal", principal_id, name or "Opdrachtgever", "Opdrachtgevergegevens bijgewerkt.", "Relaties")
    return RedirectResponse(_relations_url("principals", edit=principal_id, anchor="#relatie-formulier"), status_code=303)


@router.post("/api/principals/{principal_id}/delete")
def remove_principal(principal_id: int):
    delete_principal(principal_id)
    _audit("Opdrachtgever verwijderd", "principal", principal_id, f"Opdrachtgever {principal_id}", "Opdrachtgever verwijderd uit de database.", "Verwijderd")
    return RedirectResponse(_relations_url("principals", anchor="#relaties"), status_code=303)


@router.post("/api/vacancies")
def save_vacancy(
    title: str = Form(""),
    reference_number: str = Form(""),
    status: str = Form(""),
    owner: str = Form(""),
    relation_name: str = Form(""),
    location: str = Form(""),
    publication_status: str = Form(""),
    website_enabled: str = Form(""),
    indeed_enabled: str = Form(""),
    applicant_count: str = Form("0"),
    category: str = Form(""),
    subcategory: str = Form(""),
    contact_email: str = Form(""),
    contact_name: str = Form(""),
    country: str = Form(""),
    province: str = Form(""),
    internal_notes: str = Form(""),
    description: str = Form(""),
    requirements: str = Form(""),
    benefits: str = Form(""),
    region: str = Form(""),
    function_group: str = Form(""),
    employment_type: str = Form(""),
):
    record_id = create_vacancy(locals())
    _audit("Vacature aangemaakt", "vacature", record_id, title or "Vacature", "Nieuwe vacature aangemaakt.", "Vacatures")
    return RedirectResponse(f"/dashboard/vacancies?edit={record_id}", status_code=303)


@router.post("/api/vacancies/{vacancy_id}")
def edit_vacancy(
    vacancy_id: int,
    title: str = Form(""),
    reference_number: str = Form(""),
    status: str = Form(""),
    owner: str = Form(""),
    relation_name: str = Form(""),
    location: str = Form(""),
    publication_status: str = Form(""),
    website_enabled: str = Form(""),
    indeed_enabled: str = Form(""),
    applicant_count: str = Form("0"),
    category: str = Form(""),
    subcategory: str = Form(""),
    contact_email: str = Form(""),
    contact_name: str = Form(""),
    country: str = Form(""),
    province: str = Form(""),
    internal_notes: str = Form(""),
    description: str = Form(""),
    requirements: str = Form(""),
    benefits: str = Form(""),
    region: str = Form(""),
    function_group: str = Form(""),
    employment_type: str = Form(""),
):
    update_vacancy(vacancy_id, locals())
    _audit("Vacature bijgewerkt", "vacature", vacancy_id, title or "Vacature", "Vacaturegegevens en publicatievelden bijgewerkt.", "Vacatures")
    return RedirectResponse(f"/dashboard/vacancies?edit={vacancy_id}", status_code=303)


@router.post("/api/vacancies/{vacancy_id}/delete")
def remove_vacancy(vacancy_id: int):
    delete_vacancy(vacancy_id)
    _audit("Vacature verwijderd", "vacature", vacancy_id, f"Vacature {vacancy_id}", "Vacature verwijderd uit de database.", "Verwijderd")
    return RedirectResponse("/dashboard/vacancies", status_code=303)


@router.post("/api/import/otys-export")
async def import_otys_export(
    file: UploadFile = File(...),
    organization_type: str = Form(...),
    mode: str = Form("dry_run"),
):
    content = await file.read()
    rows, preview = parse_otys_csv(content, organization_type)

    result = {
        "filename": file.filename,
        "mode": mode,
        "organization_type": organization_type,
        "total_rows": preview.total_rows,
        "valid_rows": preview.valid_rows,
        "skipped_rows": preview.skipped_rows,
        "sample": preview.sample,
        "errors": preview.errors,
    }

    if mode == "import":
        result.update(import_otys_organizations(rows))

    return result


@router.post("/api/import/candidates")
async def import_candidates_export(
    file: UploadFile = File(...),
    mode: str = Form("dry_run"),
):
    content = await file.read()
    rows, preview = parse_csv(content, "candidate")
    result = {
        "filename": file.filename,
        "mode": mode,
        "target": "candidates",
        "total_rows": preview.total_rows,
        "valid_rows": preview.valid_rows,
        "skipped_rows": preview.skipped_rows,
        "sample": preview.sample,
        "errors": preview.errors,
    }
    if mode == "import":
        result.update(import_candidates(rows))
    return result


@router.post("/api/import/principals")
async def import_principals_export(
    file: UploadFile = File(...),
    mode: str = Form("dry_run"),
):
    content = await file.read()
    rows, preview = parse_csv(content, "principal")
    result = {
        "filename": file.filename,
        "mode": mode,
        "target": "principals",
        "total_rows": preview.total_rows,
        "valid_rows": preview.valid_rows,
        "skipped_rows": preview.skipped_rows,
        "sample": preview.sample,
        "errors": preview.errors,
    }
    if mode == "import":
        result.update(import_principals(rows))
    return result


@router.post("/api/import/vacancies")
async def import_vacancies_export(
    file: UploadFile = File(...),
    mode: str = Form("dry_run"),
):
    content = await file.read()
    rows, preview = parse_csv(content, "vacancy")
    result = {
        "filename": file.filename,
        "mode": mode,
        "target": "vacancies",
        "total_rows": preview.total_rows,
        "valid_rows": preview.valid_rows,
        "skipped_rows": preview.skipped_rows,
        "sample": preview.sample,
        "errors": preview.errors,
    }
    if mode == "import":
        result.update(import_vacancies(rows))
    return result
