"""Downstream Finance reporting consumer.

This layer only *presents* what the reconciliation marts already
computed. It performs no reconciliation logic of its own - the dbt marts
(`mart_finance_daily`, `mart_reconciliation_exceptions`) are the source
of truth.
"""

from finance_reconciliation.reporting.exporter import (
    export_finance_report,
)
from finance_reconciliation.reporting.models import (
    DailySummaryRow,
    ExceptionRow,
    FinanceReportData,
    FinanceReportExportResult,
)
from finance_reconciliation.reporting.repository import (
    load_finance_report_data,
)

__all__ = [
    "DailySummaryRow",
    "ExceptionRow",
    "FinanceReportData",
    "FinanceReportExportResult",
    "export_finance_report",
    "load_finance_report_data",
]
