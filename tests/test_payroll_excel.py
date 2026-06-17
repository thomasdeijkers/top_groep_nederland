import tempfile
import unittest
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



class PayrollPeriodStructureTests(unittest.TestCase):
    def test_available_payroll_period_numbers_stop_at_thirteen(self):
        with patch.object(records, "ensure_dashboard_tables", side_effect=RuntimeError("geen database")):
            numbers = records._available_payroll_period_numbers(2026, 20)

        self.assertEqual(numbers, list(range(1, records.PAYROLL_PERIODS_PER_YEAR + 1)))

    def test_create_payroll_period_rejects_period_fourteen(self):
        with patch.object(records, "ensure_dashboard_tables"):
            with self.assertRaises(ValueError):
                records.create_payroll_period({"year": "2026", "period_number": "14"})


if __name__ == "__main__":
    unittest.main()
