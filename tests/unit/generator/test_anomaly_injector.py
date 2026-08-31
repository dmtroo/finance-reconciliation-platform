from __future__ import annotations

from copy import deepcopy

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def sample_tables() -> dict[str, list[dict[str, object]]]:
    return {
        "invoices": [
            {
                "invoice_id": "INV-000001",
                "invoice_status": "PAID",
                "total_amount_minor": 9999,
            },
        ],
        "financial_events": [
            {
                "financial_event_id": "EVT-000001",
                "event_type": "CAPTURE",
                "amount_minor": 9999,
            },
        ],
    }


def test_inject_anomalies_does_not_mutate_input() -> None:
    tables = sample_tables()
    original = deepcopy(tables)

    result = inject_anomalies(
        tables
    )

    assert tables == original
    assert result.tables == original
    assert result.tables is not tables


def test_inject_anomalies_copies_rows() -> None:
    tables = sample_tables()

    result = inject_anomalies(
        tables
    )

    result.tables["invoices"][0][
        "total_amount_minor"
    ] = 12345

    assert (
        tables["invoices"][0][
            "total_amount_minor"
        ]
        == 9999
    )


def test_inject_anomalies_is_deterministic() -> None:
    tables = sample_tables()

    first = inject_anomalies(
        tables
    )

    second = inject_anomalies(
        tables
    )

    assert first == second


def test_foundation_injector_records_no_anomalies() -> None:
    result = inject_anomalies(
        sample_tables()
    )

    assert result.anomalies == []