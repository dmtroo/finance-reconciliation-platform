from __future__ import annotations

from copy import deepcopy

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)

EXPECTED_CODES = [
    "MISSING_CAPTURE",
    "CAPTURE_AMOUNT_MISMATCH",
    "DUPLICATE_CAPTURE",
    "INVALID_REFUND",
    "OVER_REFUND",
    "MISSING_SETTLEMENT",
    "LATE_SETTLEMENT",
    "SETTLEMENT_TOTAL_MISMATCH",
    "MISSING_BANK_RECEIPT",
    "BANK_AMOUNT_MISMATCH",
    "MISSING_LEDGER_POSTING",
    "LEDGER_AMOUNT_MISMATCH",
    "UNBALANCED_JOURNAL",
    "MISSING_FX_RATE",
    "FX_RATE_OUTLIER",
    "UNMAPPED_PRODUCT",
]


def test_injector_records_all_frozen_anomalies(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    actual_codes = [
        anomaly.anomaly_code
        for anomaly
        in result.anomalies
    ]

    assert (
        actual_codes
        == EXPECTED_CODES
    )


def test_injector_is_deterministic(
    clean_lifecycle_tables,
) -> None:
    first = inject_anomalies(
        clean_lifecycle_tables
    )

    second = inject_anomalies(
        clean_lifecycle_tables
    )

    assert (
        first.anomalies
        == second.anomalies
    )

    assert (
        first.tables
        == second.tables
    )


def test_injector_does_not_mutate_clean_input(
    clean_lifecycle_tables,
) -> None:
    original = deepcopy(
        clean_lifecycle_tables
    )

    inject_anomalies(
        clean_lifecycle_tables
    )

    assert (
        clean_lifecycle_tables
        == original
    )