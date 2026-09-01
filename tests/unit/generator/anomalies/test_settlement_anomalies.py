from __future__ import annotations

from datetime import datetime

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_missing_settlement_breaks_only_event_mapping(
    clean_lifecycle_tables,
) -> None:
    original_item_count = len(
        clean_lifecycle_tables[
            "settlement_items"
        ]
    )

    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "MISSING_SETTLEMENT"
    )

    mapped_event_ids = {
        str(
            item[
                "financial_event_id"
            ]
        )
        for item
        in result.tables[
            "settlement_items"
        ]
    }

    assert (
        anomaly.entity_id
        not in mapped_event_ids
    )

    assert len(
        result.tables[
            "settlement_items"
        ]
    ) == original_item_count


def test_late_settlement_has_six_day_delay(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "LATE_SETTLEMENT"
    )

    event = next(
        row
        for row
        in result.tables[
            "financial_events"
        ]
        if str(
            row[
                "financial_event_id"
            ]
        )
        == anomaly.entity_id
    )

    settlement_item = next(
        row
        for row
        in result.tables[
            "settlement_items"
        ]
        if str(
            row[
                "financial_event_id"
            ]
        )
        == anomaly.entity_id
    )

    settlement = next(
        row
        for row
        in result.tables[
            "settlements"
        ]
        if str(
            row["settlement_id"]
        )
        == str(
            settlement_item[
                "settlement_id"
            ]
        )
    )

    event_at = (
        event["event_at"]
    )

    assert isinstance(
        event_at,
        datetime,
    )

    event_date = (
        event_at.date()
    )

    settlement_date = (
        settlement[
            "settlement_date"
        ]
    )

    assert (
        settlement_date
        - event_date
    ).days == 6

    assert (
        event["currency"]
        == "EUR"
    )