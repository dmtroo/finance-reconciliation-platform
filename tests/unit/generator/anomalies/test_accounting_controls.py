from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_missing_ledger_posting_breaks_source_reference(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "MISSING_LEDGER_POSTING"
    )

    matching_lines = [
        line
        for line
        in result.tables[
            "journal_lines"
        ]
        if (
            str(
                line[
                    "source_reference_type"
                ]
            )
            == "FINANCIAL_EVENT"
            and str(
                line[
                    "source_reference"
                ]
            )
            == anomaly.entity_id
        )
    ]

    assert matching_lines == []


def test_ledger_amount_mismatch_remains_balanced(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "LEDGER_AMOUNT_MISMATCH"
    )

    lines = [
        line
        for line
        in result.tables[
            "journal_lines"
        ]
        if str(
            line[
                "source_reference"
            ]
        )
        == anomaly.entity_id
    ]

    total_debit = sum(
        int(
            line[
                "debit_eur_minor"
            ]
        )
        for line in lines
    )

    total_credit = sum(
        int(
            line[
                "credit_eur_minor"
            ]
        )
        for line in lines
    )

    assert (
        total_debit
        == total_credit
    )

    assert (
        anomaly.clean_value
        != anomaly.anomalous_value
    )


def test_unbalanced_journal_has_debit_credit_difference(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "UNBALANCED_JOURNAL"
    )

    lines = [
        line
        for line
        in result.tables[
            "journal_lines"
        ]
        if str(
            line[
                "source_reference"
            ]
        )
        == anomaly.entity_id
    ]

    total_debit = sum(
        int(
            line[
                "debit_eur_minor"
            ]
        )
        for line in lines
    )

    total_credit = sum(
        int(
            line[
                "credit_eur_minor"
            ]
        )
        for line in lines
    )

    assert (
        total_debit
        != total_credit
    )