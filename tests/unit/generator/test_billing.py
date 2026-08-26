from datetime import date

from finance_reconciliation.generator.billing import (
    add_months,
    recurring_invoice_dates,
)


def test_add_months_clamps_end_of_month() -> None:
    assert add_months(
        date(2026, 1, 31),
        1,
    ) == date(2026, 2, 28)


def test_monthly_invoice_dates_respect_window() -> None:
    result = recurring_invoice_dates(
        started_on=date(2025, 11, 15),
        billing_interval="MONTH",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 3, 31),
        cancelled_on=None,
    )

    assert result == [
        date(2026, 1, 15),
        date(2026, 2, 15),
        date(2026, 3, 15),
    ]


def test_cancelled_subscription_stops_future_invoices() -> None:
    result = recurring_invoice_dates(
        started_on=date(2025, 12, 10),
        billing_interval="MONTH",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 3, 31),
        cancelled_on=date(2026, 2, 5),
    )

    assert result == [
        date(2026, 1, 10),
    ]