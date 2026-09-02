"""Data contracts for the Finance reporting layer.

These structures carry mart rows from the repository to the exporter.
They hold no Finance calculations - reconciliation rate, exception
status, amount differences and the like are produced by dbt and simply
passed through.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

# Finance-facing subset of mart_finance_daily, in Daily Summary column
# order. Grain: business_date x product_id x currency.
DAILY_SUMMARY_FIELDS: tuple[str, ...] = (
    "business_date",
    "product_id",
    "product_name",
    "product_family",
    "currency",
    "invoice_count",
    "capture_count",
    "capture_amount",
    "valued_capture_amount_eur",
    "unvalued_capture_count",
    "reconciled_capture_amount_eur",
    "open_break_capture_amount_eur",
    "amount_reconciliation_rate",
    "refund_amount",
    "chargeback_amount",
    "exception_count",
    "open_break_exception_count",
    "critical_exception_count",
    "gross_exception_amount_eur",
)

# Investigation-facing subset of mart_reconciliation_exceptions, in
# Exceptions column order. Keeps the identifiers Finance needs to chase a
# specific invoice / payment / settlement.
EXCEPTION_FIELDS: tuple[str, ...] = (
    "exception_id",
    "exception_code",
    "exception_status",
    "severity",
    "entity_type",
    "entity_id",
    "business_date",
    "product_id",
    "product_name",
    "currency",
    "exception_amount_eur",
    "age_days",
    "observed_amount_eur",
    "expected_amount_eur",
    "difference_amount_eur",
    "control_source",
)


@dataclass(frozen=True)
class DailySummaryRow:
    business_date: date
    product_id: str | None
    product_name: str | None
    product_family: str | None
    currency: str
    invoice_count: int
    capture_count: int
    capture_amount: Decimal
    valued_capture_amount_eur: Decimal
    unvalued_capture_count: int
    reconciled_capture_amount_eur: Decimal
    open_break_capture_amount_eur: Decimal
    amount_reconciliation_rate: Decimal | None
    refund_amount: Decimal
    chargeback_amount: Decimal
    exception_count: int
    open_break_exception_count: int
    critical_exception_count: int
    gross_exception_amount_eur: Decimal

    def as_row(self) -> tuple[object, ...]:
        return tuple(
            getattr(self, name)
            for name in DAILY_SUMMARY_FIELDS
        )


@dataclass(frozen=True)
class ExceptionRow:
    exception_id: str
    exception_code: str
    exception_status: str
    severity: str
    entity_type: str
    entity_id: str
    business_date: date
    product_id: str | None
    product_name: str | None
    currency: str
    exception_amount_eur: Decimal | None
    age_days: int | None
    observed_amount_eur: Decimal | None
    expected_amount_eur: Decimal | None
    difference_amount_eur: Decimal | None
    control_source: str

    def as_row(self) -> tuple[object, ...]:
        return tuple(
            getattr(self, name)
            for name in EXCEPTION_FIELDS
        )


@dataclass(frozen=True)
class FinanceReportData:
    """Everything the exporter needs, straight from the marts."""

    daily: tuple[DailySummaryRow, ...]
    exceptions: tuple[ExceptionRow, ...]


@dataclass(frozen=True)
class FinanceReportExportResult:
    output_path: Path
    daily_row_count: int
    exception_row_count: int
