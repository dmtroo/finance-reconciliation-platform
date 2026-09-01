from __future__ import annotations

from finance_reconciliation.generator.anomalies.injector import (
    inject_anomalies,
)


def test_unmapped_product_references_missing_product(
    clean_lifecycle_tables,
) -> None:
    result = inject_anomalies(
        clean_lifecycle_tables
    )

    anomaly = next(
        item
        for item in result.anomalies
        if item.anomaly_code
        == "UNMAPPED_PRODUCT"
    )

    invoice = next(
        row
        for row
        in result.tables[
            "invoices"
        ]
        if str(
            row["invoice_id"]
        )
        == anomaly.entity_id
    )

    product_ids = {
        str(
            row["product_id"]
        )
        for row
        in result.tables[
            "products"
        ]
    }

    assert (
        str(
            invoice["product_id"]
        )
        not in product_ids
    )