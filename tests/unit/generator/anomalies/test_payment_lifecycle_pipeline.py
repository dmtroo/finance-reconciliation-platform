from __future__ import annotations

from copy import deepcopy

from finance_reconciliation.generator.anomalies.payment_lifecycle import (
    inject_payment_lifecycle_anomalies,
)

EXPECTED_CODES = [
    "MISSING_CAPTURE",
    "CAPTURE_AMOUNT_MISMATCH",
    "DUPLICATE_CAPTURE",
    "INVALID_REFUND",
    "OVER_REFUND",
    "MISSING_SETTLEMENT",
    "LATE_SETTLEMENT",
]


def test_payment_lifecycle_injects_expected_anomalies(
    clean_lifecycle_tables,
) -> None:
    tables = deepcopy(
        clean_lifecycle_tables
    )

    anomalies = (
        inject_payment_lifecycle_anomalies(
            tables
        )
    )

    actual_codes = [
        anomaly.anomaly_code
        for anomaly in anomalies
    ]

    assert (
        actual_codes
        == EXPECTED_CODES
    )


def test_payment_lifecycle_is_deterministic(
    clean_lifecycle_tables,
) -> None:
    first_tables = deepcopy(
        clean_lifecycle_tables
    )

    second_tables = deepcopy(
        clean_lifecycle_tables
    )

    first = (
        inject_payment_lifecycle_anomalies(
            first_tables
        )
    )

    second = (
        inject_payment_lifecycle_anomalies(
            second_tables
        )
    )

    assert first == second

    assert (
        first_tables
        == second_tables
    )