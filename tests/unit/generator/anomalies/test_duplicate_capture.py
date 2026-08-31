from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_duplicate_capture_creates_two_captures_for_one_invoice(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "DUPLICATE_CAPTURE"
    )

    target_attempt_id = str(
        anomaly.anomalous_value
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

    target_invoice_id = str(
        attempts_by_id[
            target_attempt_id
        ]["invoice_id"]
    )

    target_captures = [
        event
        for event
        in result.tables[
            "financial_events"
        ]
        if (
            event["event_type"]
            == "CAPTURE"
            and str(
                attempts_by_id[
                    str(
                        event[
                            "payment_attempt_id"
                        ]
                    )
                ]["invoice_id"]
            )
            == target_invoice_id
        )
    ]

    assert (
        len(target_captures)
        == 2
    )

    assert len(
        {
            int(
                capture[
                    "amount_minor"
                ]
            )
            for capture
            in target_captures
        }
    ) == 1


def test_duplicate_capture_donor_no_longer_looks_paid(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "DUPLICATE_CAPTURE"
    )

    donor_attempt_id = str(
        anomaly.clean_value
    )

    donor_attempt = next(
        attempt
        for attempt
        in result.tables[
            "payment_attempts"
        ]
        if str(
            attempt[
                "payment_attempt_id"
            ]
        )
        == donor_attempt_id
    )

    donor_invoice_id = str(
        donor_attempt[
            "invoice_id"
        ]
    )

    donor_invoice = next(
        invoice
        for invoice
        in result.tables[
            "invoices"
        ]
        if str(
            invoice["invoice_id"]
        )
        == donor_invoice_id
    )

    assert (
        donor_attempt["status"]
        == "DECLINED"
    )

    assert (
        donor_invoice["invoice_status"]
        == "UNCOLLECTIBLE"
    )