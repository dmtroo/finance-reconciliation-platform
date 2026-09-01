from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_settlement_total_mismatch_breaks_header_item_total(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "SETTLEMENT_TOTAL_MISMATCH"
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
        == anomaly.entity_id
    )

    items = [
        row
        for row
        in result.tables[
            "settlement_items"
        ]
        if str(
            row["settlement_id"]
        )
        == anomaly.entity_id
    ]

    item_gross = sum(
        int(
            row[
                "settlement_gross_eur_minor"
            ]
        )
        for row in items
    )

    assert (
        item_gross
        != int(
            settlement[
                "gross_amount_minor"
            ]
        )
    )