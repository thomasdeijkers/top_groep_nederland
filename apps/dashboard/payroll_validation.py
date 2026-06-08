from decimal import Decimal

from apps.dashboard.payroll_calculations import compare_values


def build_control_difference(field_key: str, label: str, excel_value, dashboard_value, tolerance: Decimal = Decimal("0.05")) -> dict:
    comparison = compare_values(excel_value, dashboard_value, tolerance)
    return {
        "field_key": field_key,
        "label": label,
        **comparison,
    }
