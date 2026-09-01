from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_invalid_refund_points_to_missing_capture(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "INVALID_REFUND"
    )

    refund = next(
        event
        for event
        in result.tables[
            "financial_events"
        ]
        if str(
            event[
                "financial_event_id"
            ]
        )
        == anomaly.entity_id
    )

    capture_ids = {
        str(
            event[
                "financial_event_id"
            ]
        )
        for event
        in result.tables[
            "financial_events"
        ]
        if event["event_type"]
        == "CAPTURE"
    }

    assert (
        str(
            refund[
                "original_capture_id"
            ]
        )
        not in capture_ids
    )


def test_over_refund_exceeds_capture_amount(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "OVER_REFUND"
    )

    refund = next(
        event
        for event
        in result.tables[
            "financial_events"
        ]
        if str(
            event[
                "financial_event_id"
            ]
        )
        == anomaly.entity_id
    )

    capture = next(
        event
        for event
        in result.tables[
            "financial_events"
        ]
        if str(
            event[
                "financial_event_id"
            ]
        )
        == str(
            refund[
                "original_capture_id"
            ]
        )
    )

    assert (
        int(
            refund[
                "amount_minor"
            ]
        )
        > int(
            capture[
                "amount_minor"
            ]
        )
    )