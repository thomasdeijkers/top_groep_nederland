import tempfile
import zipfile
from io import BytesIO
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from apps.dashboard import openai_usage, records, router as dashboard_router, timesheet_corrections, timesheet_parser, timesheet_uploads
from apps.dashboard.payroll_calculations import derived_period_total_rows
from apps.dashboard.payroll_excel import analyze_payroll_workbook, build_payroll_output_workbook


try:
    from openpyxl import Workbook, load_workbook
except ImportError:  # pragma: no cover
    Workbook = None


@unittest.skipIf(Workbook is None, "openpyxl is niet beschikbaar")
class PayrollExcelAnalysisTests(unittest.TestCase):
    def test_analyzes_period_five_reference_structure(self):
        workbook = Workbook()
        workbook.active.title = "Periode"
        workbook["Periode"]["A1"] = "Werknemer"
        workbook["Periode"]["B1"] = "Contracturen"
        workbook["Periode"]["C1"] = "Bruto uurloon"

        for sheet_name in ["WK17", "WK18", "WK19", "WK20"]:
            sheet = workbook.create_sheet(sheet_name)
            sheet["A1"] = "Werknemer"
            sheet["B1"] = "Uren gewerkt"
            sheet["C1"] = "Netto voorschot"
            sheet["D2"] = "=B2+C2"

        payslip = workbook.create_sheet("Loonstrook")
        payslip["A1"] = "werknemer"
        payslip["B1"] = "totale uren gewerkt"
        payslip["C1"] = "nog te ontvangen netto loon"
        workbook.create_sheet("Grondslag bouw & infra")
        workbook.create_sheet("SAVG")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "TGN verloning 2026 Periode 5.xlsx"
            workbook.save(path)
            analysis = analyze_payroll_workbook(path)

        self.assertEqual([week["week_number"] for week in analysis["week_tabs"]], [17, 18, 19, 20])
        self.assertEqual(analysis["period_sheet"], "Periode")
        self.assertEqual(analysis["payslip_sheet"], "Loonstrook")
        self.assertIn("Grondslag bouw & infra", analysis["foundation_sheets"])
        self.assertGreaterEqual(analysis["formula_count"], 4)
        self.assertIn("worked_hours", analysis["mapped_fields"]["WK17"])


class PayrollCalculationTests(unittest.TestCase):
    def test_decimal_hours_keep_fraction_with_dot_or_comma(self):
        from apps.dashboard import payroll_calculations

        self.assertEqual(payroll_calculations._decimal("37.5"), payroll_calculations.Decimal("37.5"))
        self.assertEqual(payroll_calculations._decimal("37,5"), payroll_calculations.Decimal("37.5"))
        self.assertEqual(payroll_calculations._decimal("5.156,25"), payroll_calculations.Decimal("5156.25"))

    def test_derives_period_totals_from_existing_payroll_rows(self):
        rows = derived_period_total_rows(
            [
                {
                    "employee_name": "Thomas",
                    "worked_days": 4,
                    "total_hours": "32",
                    "gross_amount": "€ 800,00",
                }
            ]
        )

        self.assertEqual(rows[0]["employee_name"], "Thomas")
        self.assertEqual(rows[0]["total_worked_hours"], "32")
        self.assertEqual(rows[0]["total_period_amount"], "€ 800,00")
        self.assertEqual(rows[0]["status"], "concept")

    @unittest.skipIf(Workbook is None, "openpyxl is niet beschikbaar")
    def test_exports_workbook_tabs(self):
        period = {
            "workbook_tabs": [
                {
                    "label": "WK17",
                    "columns": [{"label": "Werknemer", "key": "employee_name"}],
                    "rows": [{"employee_name": "Thomas"}],
                },
                {
                    "label": "Periode",
                    "columns": [{"label": "Werknemer", "key": "employee_name"}],
                    "rows": [{"employee_name": "Thomas"}],
                },
                {
                    "label": "Loonstrook",
                    "columns": [{"label": "Werknemer", "key": "employee_name"}],
                    "rows": [{"employee_name": "Thomas"}],
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "output.xlsx"
            build_payroll_output_workbook(path, period)
            workbook = load_workbook(path)

        self.assertEqual(workbook.sheetnames, ["WK17", "Periode", "Loonstrook"])

    def test_week_workbook_rows_link_to_timesheets(self):
        from apps.dashboard.payroll_calculations import WEEK_SHEET_COLUMNS, build_week_sheet_rows

        week = {"week_index": 1, "week_number": 18}
        rows = build_week_sheet_rows(
            "WK18",
            [{"id": 7, "name": "Thomas"}],
            [{"employee_name": "Thomas", "week_hours": ["8", "0", "0", "0"], "week_timesheet_ids": [[44], [], [], []]}],
            week,
        )
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")

        self.assertIn({"label": "Urenbriefje", "key": "timesheet_link"}, WEEK_SHEET_COLUMNS)
        self.assertEqual(rows[0]["timesheet_id"], 44)
        self.assertEqual(rows[0]["timesheet_link"], "Open")
        self.assertIn("payroll-workbook-link", template)
        self.assertIn("timesheet={{ row.timesheet_id }}", template)

    def test_workbook_editable_fields_recalculate_like_excel(self):
        week_row = {
            "worked_hours": "37.5",
            "worked_days": "5",
            "commute_km": "150",
            "work_km": "12,5",
            "single_trip_km": "15",
        }
        records._recalculate_payroll_derived_cells({"kind": "week"}, week_row)
        self.assertEqual(week_row["worked_hours"], "37.5")
        self.assertEqual(week_row["net_amount"], f"{chr(8364)} 515,63")
        self.assertEqual(week_row["total_km"], "162.5")

        period_row = {"contract_hours": "40", "gross_hourly_wage": f"{chr(8364)} 21,50"}
        records._recalculate_payroll_derived_cells({"kind": "period"}, period_row)
        self.assertEqual(period_row["gross_total"], f"{chr(8364)} 860,00")
        self.assertEqual(period_row["labor_cost_margin"], f"{chr(8364)} 154,80")

        script = Path("apps/dashboard/static/dashboard.js").read_text(encoding="utf-8-sig")
        self.assertIn("input.dataset.tabLabel.startsWith(\"WK\")", script)
        self.assertIn("gross-total", script)
        self.assertIn("normalized.includes(\",\") && normalized.includes(\".\")", script)



class PayrollRunningBalanceTests(unittest.TestCase):
    def test_running_balance_migration_tracks_required_balance_types(self):
        migration = Path("migrations/036_payroll_running_balances.sql").read_text(encoding="utf-8")

        self.assertIn("payroll_running_balance_accounts", migration)
        self.assertIn("payroll_running_balance_mutations", migration)
        self.assertIn("'wkr'", migration)
        self.assertIn("'loan_advance'", migration)
        self.assertIn("'choice_budget'", migration)
        self.assertIn("balance_year INTEGER NOT NULL DEFAULT 0", migration)

    def test_wkr_balance_status_warns_near_limit(self):
        self.assertEqual(records._running_balance_status("wkr", "2400", "2200"), "let op")
        self.assertEqual(records._running_balance_status("wkr", "2400", "2500"), "boven maximum")
        self.assertEqual(records._running_balance_status("loan_advance", None, "100"), "actief")



class PayrollPeriodSettlementTests(unittest.TestCase):
    def test_period_settlement_migration_creates_employee_period_totals(self):
        migration = Path("migrations/035_payroll_period_settlements.sql").read_text(encoding="utf-8")

        self.assertIn("payroll_period_settlements", migration)
        self.assertIn("advance_weeks_1_3", migration)
        self.assertIn("week_4_amount", migration)
        self.assertIn("total_period_amount", migration)

    def test_period_settlement_migration_supports_four_weekly_payment(self):
        migration = Path("migrations/035_payroll_period_settlements.sql").read_text(encoding="utf-8")

        self.assertIn("payment_schedule", migration)
        self.assertIn("four_weekly", migration)
        self.assertIn("total_period_amount", migration)



class PayrollWeekResultTests(unittest.TestCase):

    def test_employee_week_result_status_prioritizes_missing_data(self):
        self.assertEqual(records._employee_week_result_status(1, 1, 0), "mist inrichting")
        self.assertEqual(records._employee_week_result_status(1, 0, 1), "mist netto basisloon")
        self.assertEqual(records._employee_week_result_status(1, 0, 0), "concept")
        self.assertEqual(records._employee_week_result_status(0, 0, 0), "controle")
    def test_week_result_migration_creates_calculation_outputs(self):
        migration = Path("migrations/034_payroll_week_results.sql").read_text(encoding="utf-8")

        self.assertIn("payroll_week_results", migration)
        self.assertIn("net_wage_amount", migration)
        self.assertIn("travel_amount", migration)
        self.assertIn("day_allowance_amount", migration)
        self.assertIn("net_week_total", migration)

    def test_week_result_migration_tracks_missing_inputs(self):
        migration = Path("migrations/034_payroll_week_results.sql").read_text(encoding="utf-8")

        self.assertIn("mist_inrichting", migration)
        self.assertIn("mist_netto_basisloon", migration)
        self.assertIn("travel_km_net_uta", migration)
        self.assertIn("travel_km_net_build", migration)



class PayrollWeekInputTests(unittest.TestCase):
    def test_week_input_migration_creates_normalized_layers(self):
        migration = Path("migrations/033_payroll_week_inputs.sql").read_text(encoding="utf-8")

        self.assertIn("payroll_week_inputs", migration)
        self.assertIn("payroll_week_input_days", migration)
        self.assertIn("payroll_week_input_projects", migration)
        self.assertIn("idx_payroll_week_inputs_timesheet", migration)

    def test_week_input_days_cover_full_week(self):
        migration = Path("migrations/033_payroll_week_inputs.sql").read_text(encoding="utf-8")

        for day_name in ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]:
            self.assertIn(day_name, migration)

    def test_week_input_uses_calculated_km_when_total_is_missing(self):
        migration = Path("migrations/033_payroll_week_inputs.sql").read_text(encoding="utf-8")

        self.assertIn("calculated_total_km", migration)
        self.assertLess(
            migration.index("w.parsed_fields->'total_km'"),
            migration.index("w.parsed_fields->'calculated_total_km'"),
        )

    def test_parser_fills_total_km_from_day_km_when_total_missing(self):
        fields = {
            "monday_km": {"value": "34", "confidence": 98},
            "tuesday_km": {"value": "", "confidence": 0},
            "wednesday_km": {"value": "", "confidence": 0},
            "thursday_km": {"value": "", "confidence": 0},
            "friday_km": {"value": "", "confidence": 0},
            "saturday_km": {"value": "", "confidence": 0},
            "sunday_km": {"value": "", "confidence": 0},
            "total_km": {"value": "", "confidence": 0},
        }

        timesheet_parser._check_total_km(fields)

        self.assertEqual(fields["calculated_total_km"]["value"], "34")
        self.assertEqual(fields["total_km"]["value"], "34")
        self.assertEqual(fields["total_km_check"]["value"], "klopt")

    def test_corrections_materialize_missing_km_total_from_day_km(self):
        fields = {
            "monday_km": {"value": "34", "confidence": 98, "verified": True},
            "total_km": {"value": "", "confidence": 0},
        }

        timesheet_corrections._recalculate_total_checks(fields)

        self.assertEqual(fields["calculated_total_km"]["value"], "34")
        self.assertEqual(fields["total_km"]["value"], "34")
        self.assertEqual(fields["total_km_check"]["value"], "klopt")



class PayrollEmployeeArrangementTests(unittest.TestCase):
    def test_arrangement_migration_limits_period_numbers_to_thirteen(self):
        migration = Path("migrations/032_payroll_employee_arrangements.sql").read_text(encoding="utf-8")

        self.assertIn("valid_from_period_number BETWEEN 1 AND 13", migration)
        self.assertIn("payroll_employee_rights", migration)
        self.assertIn("payroll_employee_allowances", migration)

    def test_arrangement_payment_schedule_labels_are_documented(self):
        migration = Path("migrations/032_payroll_employee_arrangements.sql").read_text(encoding="utf-8")

        self.assertIn("'weekly'", migration)
        self.assertIn("'four_weekly'", migration)



class PayrollParameterTests(unittest.TestCase):
    def test_formats_parameter_percentages_for_display(self):
        self.assertEqual(records._format_parameter_value("0.0833", "percentage"), "8.33%")
        self.assertEqual(records._format_parameter_value("0.0800", "percentage"), "8%")

    def test_formats_parameter_money_for_display(self):
        self.assertIn("0,28", records._format_parameter_value("0.28", "euro_per_km"))



class PayrollPhaseStatusTests(unittest.TestCase):
    def test_phase_status_blocks_without_week_results(self):
        status = records.payroll_phase_status({"result_count": 0}, {"blocking": 0, "warning": 0, "total": 0})

        self.assertFalse(status["can_approve"])
        self.assertEqual(status["label"], "Nog niet berekend")
        self.assertIn("geen gevalideerde uren", status["detail"])

    def test_phase_status_blocks_known_exceptions(self):
        status = records.payroll_phase_status({"result_count": 4}, {"blocking": 1, "warning": 2, "total": 3})

        self.assertFalse(status["can_approve"])
        self.assertEqual(status["tone"], "danger")

    def test_phase_status_allows_approval_with_warnings_only(self):
        status = records.payroll_phase_status({"result_count": 4}, {"blocking": 0, "warning": 1, "total": 1})

        self.assertTrue(status["can_approve"])
        self.assertEqual(status["label"], "Nalopen voor akkoord")


class PayrollExceptionTests(unittest.TestCase):
    def test_exception_summary_counts_severities(self):
        summary = records.summarize_payroll_exceptions([
            {"severity": "blokkerend"},
            {"severity": "waarschuwing"},
            {"severity": "waarschuwing"},
            {"severity": "info"},
        ])

        self.assertEqual(summary, {"total": 4, "blocking": 1, "warning": 2, "info": 1})

    def test_exception_severity_labels_match_period_ui(self):
        self.assertEqual(records._payroll_exception_severity_label("blokkerend"), "Blokkeert")
        self.assertEqual(records._payroll_exception_severity_label("waarschuwing"), "Nalopen")
        self.assertEqual(records._payroll_exception_severity_label("anders"), "Info")


class RelationPayrollContextTests(unittest.TestCase):
    def test_relation_payroll_context_combines_employee_layers(self):
        arrangement = {"id": 11, "relation_id": 7}
        balance = {"id": 21, "relation_id": 7}
        settlement = {"period_label": "2026 P5", "relation_id": 7}

        with patch.object(records, "list_relation_payroll_employee_arrangements", return_value=[arrangement]), \
             patch.object(records, "list_relation_payroll_running_balances", return_value=[balance]), \
             patch.object(records, "list_relation_payroll_period_settlements", return_value=[settlement]):
            context = records.get_relation_payroll_context(7)

        self.assertEqual(context["current_arrangement"], arrangement)
        self.assertEqual(context["balances"], [balance])
        self.assertEqual(context["settlements"], [settlement])

    def test_relation_payroll_context_handles_empty_relation(self):
        self.assertEqual(
            records.get_relation_payroll_context(None),
            {"arrangements": [], "current_arrangement": None, "balances": [], "settlements": []},
        )


class PayrollPeriodStructureTests(unittest.TestCase):
    def test_available_payroll_period_numbers_stop_at_thirteen(self):
        with patch.object(records, "ensure_dashboard_tables", side_effect=RuntimeError("geen database")):
            numbers = records._available_payroll_period_numbers(2026, 20)

        self.assertEqual(numbers, list(range(1, records.PAYROLL_PERIODS_PER_YEAR + 1)))

    def test_create_payroll_period_rejects_period_fourteen(self):
        with patch.object(records, "ensure_dashboard_tables"):
            with self.assertRaises(ValueError):
                records.create_payroll_period({"year": "2026", "period_number": "14"})


class PayrollDatamodelFoundationTests(unittest.TestCase):
    def test_foundation_migration_creates_year_and_week_line_tables(self):
        migration = Path("migrations/037_payroll_datamodel_foundation.sql").read_text(encoding="utf-8-sig")

        self.assertIn("payroll_years", migration)
        self.assertIn("period_count INTEGER NOT NULL DEFAULT 13", migration)
        self.assertIn("weeks_per_period INTEGER NOT NULL DEFAULT 4", migration)
        self.assertIn("payroll_week_lines", migration)
        self.assertIn("cost_center", migration)
        self.assertIn("UNIQUE (payroll_week_input_id, line_index)", migration)

    def test_foundation_migration_extends_openai_audit_for_ocr_context(self):
        migration = Path("migrations/037_payroll_datamodel_foundation.sql").read_text(encoding="utf-8-sig")

        for field in [
            "purpose",
            "relation_id",
            "timesheet_inbox_id",
            "payroll_week_input_id",
            "request_hash",
            "response_hash",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "latency_ms",
        ]:
            self.assertIn(field, migration)

    def test_foundation_migration_is_part_of_dashboard_startup(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")

        self.assertIn("migrations/037_payroll_datamodel_foundation.sql", data_store)



class PayrollAuditContextTests(unittest.TestCase):
    def test_audit_context_migration_links_payroll_and_ai_ocr_records(self):
        migration = Path("migrations/042_payroll_audit_context.sql").read_text(encoding="utf-8-sig")

        for field in [
            "payroll_year_id",
            "payroll_period_id",
            "payroll_period_week_id",
            "payroll_week_input_id",
            "timesheet_inbox_id",
            "relation_id",
            "correlation_id",
            "source_channel",
        ]:
            self.assertIn(field, migration)
        self.assertIn("payroll_audit_context", migration)
        self.assertIn("payroll_ai_ocr_audit_context", migration)
        self.assertIn("payroll_period_audit_summary", migration)

    def test_audit_context_migration_is_part_of_dashboard_startup(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")

        self.assertIn("migrations/042_payroll_audit_context.sql", data_store)
        self.assertLess(
            data_store.index("migrations/038_payroll_datamodel_views.sql"),
            data_store.index("migrations/042_payroll_audit_context.sql"),
        )

    def test_audit_context_fields_are_inferred_from_entity_and_metadata(self):
        context = records._audit_context_fields(
            "payroll_period",
            12,
            {"relation_id": "7", "timesheet_inbox_id": "44", "source_channel": "test"},
        )

        self.assertEqual(context["payroll_period_id"], 12)
        self.assertEqual(context["relation_id"], 7)
        self.assertEqual(context["timesheet_inbox_id"], 44)
        self.assertEqual(context["source_channel"], "test")

    def test_openai_audit_context_defaults_to_timesheet_ocr(self):
        context = openai_usage._openai_api_audit_context(
            "whatsapp_timesheet",
            55,
            {"relation_id": "8", "total_tokens": "120"},
        )

        self.assertEqual(context["provider"], "openai")
        self.assertEqual(context["purpose"], "timesheet_ocr")
        self.assertEqual(context["timesheet_inbox_id"], 55)
        self.assertEqual(context["relation_id"], 8)
        self.assertEqual(context["total_tokens"], 120)


class PayrollDatamodelViewTests(unittest.TestCase):
    def test_datamodel_views_migration_creates_period_and_year_views(self):
        migration = Path("migrations/038_payroll_datamodel_views.sql").read_text(encoding="utf-8-sig")

        self.assertIn("payroll_year_overview", migration)
        self.assertIn("payroll_period_datamodel_status", migration)
        self.assertIn("expected_period_count", migration)
        self.assertIn("actual_week_count", migration)
        self.assertIn("week_structure_status", migration)

    def test_period_datamodel_status_tracks_foundation_layers(self):
        migration = Path("migrations/038_payroll_datamodel_views.sql").read_text(encoding="utf-8-sig")

        for field in [
            "week_input_count",
            "week_line_count",
            "week_result_count",
            "period_settlement_count",
            "employee_arrangement_count",
            "parameter_version_count",
            "running_balance_account_count",
            "audit_event_count",
            "openai_api_audit_event_count",
        ]:
            self.assertIn(field, migration)

    def test_datamodel_views_migration_is_part_of_dashboard_startup(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")

        self.assertIn("migrations/038_payroll_datamodel_views.sql", data_store)


class PayrollDatamodelRecordTests(unittest.TestCase):
    def test_datamodel_status_row_formats_counts_and_dates(self):
        row = (
            12,
            2026,
            5,
            "Periode 5 - 2026",
            date(2026, 5, 4),
            date(2026, 5, 31),
            "open",
            4,
            10,
            14,
            8,
            3,
            7,
            16,
            21,
            2,
            5,
            6,
            "ok",
            datetime(2026, 6, 17, 9, 30),
        )

        item = records._payroll_datamodel_status_row(row)

        self.assertEqual(item["period_number"], 5)
        self.assertEqual(item["week_count"], 4)
        self.assertEqual(item["week_line_count"], 14)
        self.assertEqual(item["parameter_version_count"], 16)
        self.assertEqual(item["week_structure_status"], "ok")
        self.assertEqual(item["start_date"], "04-05-2026")

    def test_year_overview_row_formats_expected_structure(self):
        row = (1, 2026, 13, 4, 2, 8, date(2026, 1, 5), date(2026, 2, 28), "active", None)

        item = records._payroll_year_overview_row(row)

        self.assertEqual(item["expected_period_count"], 13)
        self.assertEqual(item["expected_weeks_per_period"], 4)
        self.assertEqual(item["actual_week_count"], 8)
        self.assertEqual(item["status"], "active")


class PayrollDatamodelDashboardTests(unittest.TestCase):
    def test_periods_page_loads_datamodel_context(self):
        router = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")

        self.assertIn("list_payroll_year_overview", router)
        self.assertIn("list_payroll_datamodel_status", router)
        self.assertIn("payroll_year_overview", router)
        self.assertIn("payroll_datamodel_status", router)

    def test_periods_template_shows_datamodel_control_section(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        stylesheet = Path("apps/dashboard/static/dashboard.css").read_text(encoding="utf-8-sig")

        self.assertIn("datamodel-controle", template)
        self.assertIn("Fundament jaar, periodes en payroll-lagen", template)
        self.assertIn("week_line_count", template)
        self.assertIn("openai_api_audit_event_count", template)
        self.assertIn(".datamodel-check", stylesheet)

class PayrollPeriodDatamodelDetailTests(unittest.TestCase):
    def test_period_detail_attaches_datamodel_status(self):
        records_source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")

        self.assertIn("def get_payroll_period_datamodel_status", records_source)
        self.assertIn('period["datamodel_status"] = get_payroll_period_datamodel_status(period_id)', records_source)
        self.assertIn("FROM payroll_period_datamodel_status", records_source)

    def test_period_detail_template_shows_datamodel_strip(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        stylesheet = Path("apps/dashboard/static/dashboard.css").read_text(encoding="utf-8-sig")

        self.assertIn("period-datamodel-strip", template)
        self.assertIn("selected_payroll_period.datamodel_status", template)
        self.assertIn("week_line_count", template)
        self.assertIn(".period-datamodel-strip", stylesheet)

class PayrollEmptyPeriodCopyTests(unittest.TestCase):
    def test_empty_period_copy_explains_missing_validated_hours(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")

        self.assertIn("Nog geen gevalideerde uren", template)
        self.assertIn("Valideer eerst urenbriefjes", template)
        self.assertIn("gevalideerde uren in deze loonperiode", template)


class PayrollTestDataMigrationSafetyTests(unittest.TestCase):
    def test_period_two_testdata_migration_preserves_validated_statuses(self):
        migration = Path("migrations/028_payroll_period_02_test_timesheets.sql").read_text(encoding="utf-8-sig")

        self.assertIn("LOWER(REPLACE(COALESCE(w.status, ''), ' ', '_')) IN ('', 'controle', 'te_controleren', 'gematcht', 'matched')", migration)
        self.assertGreaterEqual(
            migration.count("LOWER(REPLACE(COALESCE(w.status, ''), ' ', '_')) IN ('', 'controle', 'te_controleren', 'gematcht', 'matched')"),
            4,
        )
        self.assertIn("ELSE w.status", migration)
        self.assertIn("ELSE w.validated_at", migration)
        self.assertIn("ELSE w.payroll_sent_at", migration)
        self.assertNotIn("SET status = 'controle',", migration)


class DashboardOverviewWeeklyHoursTests(unittest.TestCase):
    def test_demo_weekly_hours_are_marked_and_link_to_periods(self):
        rows = records._demo_weekly_hours_yoy()

        self.assertTrue(rows)
        self.assertTrue(all(row["is_demo"] for row in rows))
        self.assertTrue(all(row["source_label"] == "Demo" for row in rows))
        self.assertTrue(all(row["href"] == "/dashboard/periods#periodes" for row in rows))

    def test_weekly_hours_cards_are_clickable(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")

        self.assertIn("href=\"{{ week.href|default('/dashboard/periods#periodes') }}\"", template)
        self.assertIn("hours-yoy-card--demo", template)
        self.assertIn("voorbeelddata", template)


class DashboardVisibleDemoPayrollSeedTests(unittest.TestCase):
    def test_empty_dashboard_views_trigger_visible_demo_seed(self):
        source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")

        self.assertIn("def _ensure_dashboard_tables_for_read", source)
        self.assertIn("DASHBOARD_SCHEMA_ENSURE_READ_WARNING", source)
        self.assertIn("def ensure_visible_demo_payroll_data", source)
        self.assertIn("migrations/039_full_year_test_payroll.sql", source)
        self.assertIn("migrations/041_dashboard_demo_payroll.sql", source)
        self.assertIn("migrations/033_payroll_week_inputs.sql", source)
        self.assertIn("DASHBOARD_DEMO_PAYROLL_SEED_STEP_ERROR", source)
        runtime_source = source[source.index("def get_overview_data"):]
        self.assertNotIn("ensure_visible_demo_payroll_data()", runtime_source)
        self.assertGreaterEqual(source.count("_ensure_dashboard_tables_for_read()"), 10)

    def test_payroll_archive_is_a_real_tab_panel(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        script = Path("apps/dashboard/static/dashboard.js").read_text(encoding="utf-8-sig")

        self.assertIn("data-period-tabs", template)
        self.assertIn("data-period-tab=\"archive\"", template)
        self.assertIn("data-period-panel=\"archive\"", template)
        self.assertIn("hidden", template)
        self.assertIn("data-period-panel", script)
        self.assertIn("#periode-archief", script)

    def test_period_page_ensures_full_2026_calendar_without_timesheets(self):
        source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")

        self.assertIn("def ensure_payroll_period_calendar", source)
        self.assertIn("PAYROLL_CALENDAR_START_2026", source)
        self.assertIn("range(1, PAYROLL_PERIODS_PER_YEAR + 1)", source)
        self.assertIn("INSERT INTO payroll_periods", source)
        self.assertIn("INSERT INTO payroll_period_weeks", source)
        self.assertIn("ensure_payroll_period_calendar(2026)", source)
        list_periods_block = source[source.index("def list_payroll_periods"):source.index("def get_payroll_data_diagnostics")]
        self.assertNotIn("ensure_visible_demo_payroll_data()", list_periods_block)

class PayrollDataDiagnosticsTests(unittest.TestCase):
    def test_periods_page_loads_payroll_data_diagnostics(self):
        router = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        records_source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")

        self.assertIn("def get_payroll_data_diagnostics", records_source)
        self.assertIn("get_payroll_data_diagnostics", router)
        self.assertIn("payroll_data_diagnostics", router)
        self.assertIn("payroll-data-controle", template)
        self.assertIn("Echte tabeldata", template)
        self.assertIn("Projectboekingen", records_source)
        self.assertIn("AI/OCR audit", records_source)


class CompletePeriodTimesheetImportTests(unittest.TestCase):
    def test_zip_import_iterates_supported_documents_only(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("deel/A weekstaat 21 2026.jpeg", b"image")
            archive.writestr("deel/B weekstaat 21 2026.pdf", b"pdf")
            archive.writestr("deel/notitie.docx", b"docx")

        docs = list(timesheet_uploads._iter_import_documents("periode.zip", buffer.getvalue()))

        self.assertEqual(len(docs), 2)
        self.assertTrue(docs[0][0].startswith("periode/"))
        self.assertTrue(any(name.endswith(".pdf") for name, _ in docs))

    def test_complete_period_import_ui_and_route_are_present(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")
        upload_source = Path("apps/dashboard/timesheet_uploads.py").read_text(encoding="utf-8-sig")

        self.assertIn("/api/whatsapp/complete-period-import", template)
        self.assertIn("Upload testset", template)
        self.assertIn("complete-period-import", router_source)
        self.assertIn("replace_complete_period_import", upload_source)
        self.assertIn("project_time_bookings", upload_source)

    def test_timesheet_upload_falls_back_when_candidate_fk_is_stale(self):
        upload_source = Path("apps/dashboard/timesheet_uploads.py").read_text(encoding="utf-8-sig")

        self.assertIn("from psycopg2.errors import ForeignKeyViolation", upload_source)
        insert_block = upload_source.split("INSERT INTO whatsapp_timesheet_inbox", 1)[1].split("RETURNING id", 1)[0]
        self.assertNotIn("matched_candidate_id", insert_block)
        self.assertIn("except ForeignKeyViolation", upload_source)
        self.assertIn('status = "te_controleren"', upload_source)

    def test_legacy_timesheet_candidate_fk_is_removed_by_migration(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")
        migration = Path("migrations/046_clear_legacy_timesheet_candidate_fk.sql").read_text(encoding="utf-8-sig")
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")

        self.assertIn("046_clear_legacy_timesheet_candidate_fk.sql", data_store)
        self.assertIn("whatsapp_timesheet_inbox", migration)
        self.assertIn("matched_candidate_id", migration)
        self.assertIn("DROP CONSTRAINT", migration)
        self.assertIn("_db_error_detail", router_source)
        self.assertIn("constraint_name", router_source)

    def test_payroll_test_workspace_can_be_cleared_from_ui(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")
        records_source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")

        self.assertIn("/api/test/payroll-workspace/clear", template)
        self.assertIn("Reset testdata", template)
        self.assertIn("def clear_payroll_workspace_for_testing", router_source)
        self.assertIn("clear_payroll_test_workspace", router_source)
        self.assertNotIn("cleared_periods", router_source)
        self.assertIn("def _truncate_existing_tables", records_source)
        self.assertIn("TRUNCATE TABLE", records_source)
        self.assertIn("project_time_bookings", records_source)
        self.assertIn("whatsapp_timesheet_inbox", records_source)
        self.assertIn("Loonperiodes zijn behouden", records_source)
        self.assertIn("payroll_week_inputs", records_source)
        self.assertIn("payroll_week_results", records_source)
        self.assertIn("payroll_period_settlements", records_source)
        self.assertIn("openai_api_audit_events", records_source)
        self.assertIn("_payroll_demo_seed_is_suppressed", records_source)
        self.assertIn("cleared_payroll_rows", router_source)

    def test_test_data_controls_are_visually_grouped(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        stylesheet = Path("apps/dashboard/static/dashboard.css").read_text(encoding="utf-8-sig")
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")

        self.assertIn("test-data-panel", template)
        self.assertIn("Upload testset", template)
        self.assertIn("test-file-input", template)
        self.assertIn("test-action-button--primary", template)
        self.assertIn("test-action-button--danger", template)
        self.assertIn("Reset testdata", template)
        self.assertIn("De loonperiodes zelf blijven staan", template)
        self.assertNotIn("loonperiodes voor deze testomgeving legen", template)
        self.assertIn(".test-data-panel", stylesheet)
        self.assertIn(".test-file-input", stylesheet)
        self.assertIn("@router.get(\"/api/whatsapp/complete-period-import\")", router_source)
        self.assertIn("upload_error", router_source)
        self.assertIn("import_error", template)

    def test_test_seeds_are_suppressed_after_reset_and_deploy_clears_once(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")
        migration = Path("migrations/043_reset_payroll_test_dataset_once.sql").read_text(encoding="utf-8-sig")
        fast_migration = Path("migrations/044_fast_reset_payroll_test_dataset_once.sql").read_text(encoding="utf-8-sig")
        restore_migration = Path("migrations/045_restore_payroll_period_calendar.sql").read_text(encoding="utf-8-sig")

        self.assertIn("_payroll_test_seed_is_suppressed", data_store)
        self.assertLess(
            data_store.index("migrations/021_audit_events.sql"),
            data_store.index("migrations/022_otys_staging_tables.sql"),
        )
        self.assertNotIn("043_reset_payroll_test_dataset_once.sql", data_store)
        self.assertNotIn("044_fast_reset_payroll_test_dataset_once.sql", data_store)
        self.assertIn("045_restore_payroll_period_calendar.sql", data_store)
        self.assertNotIn("migrations/019_demo_seed_data.sql", data_store)
        self.assertNotIn("migrations/040_one_period_test_hours.sql", data_store)
        self.assertIn("deploy_reset_043", migration)
        self.assertIn("deploy_reset_044", fast_migration)
        self.assertIn("TRUNCATE TABLE", migration)
        self.assertIn("TRUNCATE TABLE", fast_migration)
        self.assertIn("whatsapp_timesheet_inbox", migration)
        self.assertIn("payroll_periods", migration)
        self.assertIn("openai_api_audit_events", migration)
        self.assertIn("Testfase uren en loonperiodes geleegd", migration)
        self.assertIn("Herstelde loonperiodekalender", restore_migration)
        self.assertIn("generate_series(1, 13)", restore_migration)
        self.assertIn("payroll_period_weeks", restore_migration)

    def test_audit_context_migration_ignores_deleted_test_records(self):
        migration = Path("migrations/042_payroll_audit_context.sql").read_text(encoding="utf-8-sig")

        self.assertIn("FROM whatsapp_timesheet_inbox w", migration)
        self.assertIn("WHERE w.id = e.entity_id", migration)
        self.assertIn("WHERE w.id = a.source_id", migration)
        self.assertIn("FROM relations r", migration)
        self.assertIn("FROM payroll_periods p", migration)
        self.assertIn("FROM payroll_week_inputs i", migration)

    def test_payslip_manual_net_received_recalculates_remaining_net(self):
        row = {
            "period_total": f"{chr(8364)} 1707,06",
            "already_received_net": "500",
            "payslip_advance": f"{chr(8364)} 0,00",
            "net_to_receive": f"{chr(8364)} 1707,06",
            "net_total": f"{chr(8364)} 1707,06",
        }

        records._recalculate_payroll_derived_cells({"kind": "payslip"}, row)

        self.assertEqual(row["net_to_receive"], f"{chr(8364)} 1.207,06")
        self.assertEqual(row["net_total"], f"{chr(8364)} 1.207,06")


class DashboardDatabaseStatusTests(unittest.TestCase):
    def test_non_overview_pages_use_real_database_status(self):
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")

        self.assertIn("get_database_status", router_source)
        self.assertIn('"database": database_status', router_source)
        self.assertIn('"database_status"', router_source)

    def test_relation_detail_read_continues_after_schema_warning(self):
        relation_source = Path("apps/dashboard/relations.py").read_text(encoding="utf-8-sig")

        self.assertIn("RELATION_READ_SCHEMA_WARNING", relation_source)
        self.assertIn("SELECT * FROM relations WHERE id = %s", relation_source)


class TimesheetCandidateValidationTests(unittest.TestCase):
    def test_timesheet_validation_requires_candidate_and_inline_creation(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")
        corrections_source = Path("apps/dashboard/timesheet_corrections.py").read_text(encoding="utf-8-sig")
        stylesheet = Path("apps/dashboard/static/dashboard.css").read_text(encoding="utf-8-sig")

        self.assertIn("Koppel eerst een kandidaat", template)
        self.assertIn("Kandidaat aanmaken", template)
        self.assertIn("data-workflow-candidate-id", template)
        self.assertIn("data-workflow-validate-button", template)
        self.assertIn("/api/whatsapp/timesheet/{{ selected_message.id }}/candidate", template)
        self.assertIn("timesheet-create-candidate-form", template)
        self.assertIn("@router.post(\"/api/whatsapp/timesheet/{timesheet_id}/candidate\")", router_source)
        self.assertIn("create_candidate(", router_source)
        self.assertIn("save_field_corrections(", router_source)
        self.assertIn("TimesheetValidationError", corrections_source)
        self.assertIn("Koppel eerst een kandidaat", corrections_source)
        self.assertIn("relation_type = 'candidate'", corrections_source)
        self.assertIn("validate_error", router_source)
        self.assertIn("matched_relation_id: str = Form(\"\")", router_source)
        self.assertIn(".candidate-create-panel", stylesheet)
        self.assertIn(".workflow-action-note", stylesheet)

    def test_candidate_selection_enables_validation_button(self):
        script = Path("apps/dashboard/static/dashboard.js").read_text(encoding="utf-8-sig")

        self.assertIn("data-workflow-candidate-id", script)
        self.assertIn("data-workflow-validate-button", script)
        self.assertIn("validateButton.disabled = false", script)
        self.assertIn("workflowCandidateTarget.value = option.value", script)


class DashboardContextSafetyTests(unittest.TestCase):
    def test_dashboard_context_sections_fall_back_individually(self):
        def broken_loader():
            raise RuntimeError("kapot")

        self.assertEqual(dashboard_router._context_value("periods", "payroll_periods", [], broken_loader), [])

    def test_dashboard_context_logs_named_sections(self):
        router_source = Path("apps/dashboard/router.py").read_text(encoding="utf-8-sig")

        self.assertIn("DASHBOARD_CONTEXT_SECTION_ERROR", router_source)
        self.assertIn("selected_payroll_period", router_source)
        self.assertIn("timesheet_row", router_source)


class PayrollPeriodDetailSafetyTests(unittest.TestCase):
    def test_period_detail_uses_safe_defaults_and_warning(self):
        records_source = Path("apps/dashboard/records.py").read_text(encoding="utf-8-sig")
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")

        self.assertIn("def _empty_payroll_period_detail_defaults", records_source)
        self.assertIn("PAYROLL_PERIOD_DETAIL_WARNING", records_source)
        self.assertIn("detail_warning", records_source)
        self.assertIn("payroll-detail-warning", template)

    def test_period_controls_are_collapsible(self):
        template = Path("apps/dashboard/templates/dashboard.html").read_text(encoding="utf-8-sig")
        stylesheet = Path("apps/dashboard/static/dashboard.css").read_text(encoding="utf-8-sig")

        self.assertIn("payroll-control-details", template)
        self.assertIn("<summary>", template)
        self.assertIn("Controles en datamodel", template)
        self.assertIn(".payroll-control-details", stylesheet)


class PayrollFullYearTestSeedTests(unittest.TestCase):
    def test_full_year_test_seed_creates_missing_periods_and_weeks(self):
        migration = Path("migrations/039_full_year_test_payroll.sql").read_text(encoding="utf-8-sig")

        self.assertIn("generate_series(1, 13)", migration)
        self.assertIn("ON CONFLICT (year, period_number)", migration)
        self.assertIn("payroll_period_weeks", migration)
        self.assertIn("WHERE NOT EXISTS", migration)
        self.assertNotIn("whatsapp_timesheet_inbox", migration)
        self.assertNotIn("project_time_bookings", migration)

    def test_full_year_test_seed_runs_before_week_input_derivations(self):
        data_store = Path("apps/dashboard/data_store.py").read_text(encoding="utf-8-sig")

        self.assertNotIn("migrations/039_full_year_test_payroll.sql", data_store)
        self.assertNotIn("migrations/040_one_period_test_hours.sql", data_store)
        self.assertNotIn("migrations/041_dashboard_demo_payroll.sql", data_store)
        self.assertIn("migrations/033_payroll_week_inputs.sql", data_store)

    def test_one_period_test_hours_seed_populates_live_timesheets(self):
        migration = Path("migrations/040_one_period_test_hours.sql").read_text(encoding="utf-8-sig")

        self.assertIn("testdata_one_period", migration)
        self.assertIn("loon_te_berekenen", migration)
        self.assertIn("whatsapp_timesheet_inbox", migration)
        self.assertIn("project_time_bookings", migration)
        self.assertIn("test-one-period-2026", migration)
        self.assertIn("fallback_candidate", migration)

    def test_dashboard_demo_seed_populates_visible_relations_period_and_hours(self):
        migration = Path("migrations/041_dashboard_demo_payroll.sql").read_text(encoding="utf-8-sig")

        self.assertIn("dashboard_demo", migration)
        self.assertIn("dashboard-demo-candidate-001", migration)
        self.assertIn("dashboard-demo-principal-001", migration)
        self.assertIn("dashboard_demo_payroll", migration)
        self.assertIn("loon_te_berekenen", migration)
        self.assertIn("payroll_period_id", migration)
        self.assertIn("project_time_bookings", migration)
        self.assertIn("whatsapp_timesheet_inbox", migration)

if __name__ == "__main__":
    unittest.main()
