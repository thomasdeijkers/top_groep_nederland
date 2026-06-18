import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from apps.dashboard import records
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

        self.assertIn("migrations/039_full_year_test_payroll.sql", data_store)
        self.assertIn("migrations/040_one_period_test_hours.sql", data_store)
        self.assertIn("migrations/041_dashboard_demo_payroll.sql", data_store)
        self.assertLess(
            data_store.index("migrations/041_dashboard_demo_payroll.sql"),
            data_store.index("migrations/033_payroll_week_inputs.sql"),
        )
        self.assertIn("040_one_period_test_hours.sql", data_store)
        self.assertIn("041_dashboard_demo_payroll.sql", data_store)

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
