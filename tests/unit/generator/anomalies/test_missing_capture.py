from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_missing_capture_creates_paid_invoice_without_capture(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "MISSING_CAPTURE"
    )

    invoice = next(
        row
        for row
        in result.tables["invoices"]
        if str(
            row["invoice_id"]
        )
        == anomaly.entity_id
    )

    attempts_by_id = {
        str(
            attempt[
                "payment_attempt_id"
            ]
        ): attempt
        for attempt
        in result.tables[
            "payment_attempts"
        ]
    }

    capture_invoice_ids = {
        str(
            attempts_by_id[
                str(
                    event[
                        "payment_attempt_id"
                    ]
                )
            ]["invoice_id"]
        )
        for event
        in result.tables[
            "financial_events"
        ]
        if event["event_type"]
        == "CAPTURE"
    }

    assert (
        invoice["invoice_status"]
        == "PAID"
    )

    assert (
        anomaly.entity_id
        not in capture_invoice_ids
    )