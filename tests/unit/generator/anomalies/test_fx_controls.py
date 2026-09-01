from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_missing_fx_rate_moves_non_eur_event_before_fixture_period(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "MISSING_FX_RATE"
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

    timestamp = (
        event["event_at"]
    )

    assert isinstance(
        timestamp,
        datetime,
    )

    assert (
        timestamp.date().isoformat()
        == "2020-01-01"
    )

    assert (
        event["currency"]
        != "EUR"
    )


def test_fx_rate_outlier_changes_psp_rate_by_more_than_three_percent(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "FX_RATE_OUTLIER"
    )

    clean_rate = Decimal(
        str(
            anomaly.clean_value
        )
    )

    anomalous_rate = Decimal(
        str(
            anomaly.anomalous_value
        )
    )

    variance_ratio = abs(
        anomalous_rate
        / clean_rate
        - Decimal(1)
    )

    assert (
        variance_ratio
        > Decimal("0.03")
    )