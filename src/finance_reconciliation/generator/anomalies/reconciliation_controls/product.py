from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    TableRow,
    Tables,
    get_table,
)
from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    captures_by_invoice,
    payment_attempts_by_id,
)
from finance_reconciliation.generator.anomalies.selector import (
    select_first_eligible,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)

UNMAPPED_PRODUCT_ID = (
    "PROD-UNMAPPED"
)


def inject_unmapped_product(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    products = get_table(
        tables,
        "products",
    )

    invoices = get_table(
        tables,
        "invoices",
    )

    payment_attempts = get_table(
        tables,
        "payment_attempts",
    )

    financial_events = get_table(
        tables,
        "financial_events",
    )

    product_ids = {
        str(
            product["product_id"]
        )
        for product in products
    }

    attempts_by_id = (
        payment_attempts_by_id(
            payment_attempts
        )
    )

    invoice_captures = (
        captures_by_invoice(
            financial_events,
            attempts_by_id=(
                attempts_by_id
            ),
        )
    )

    def eligible(
        invoice: TableRow,
    ) -> bool:
        invoice_id = str(
            invoice["invoice_id"]
        )

        if (
            invoice_id
            in state.used_invoice_ids
        ):
            return False

        captures = (
            invoice_captures.get(
                invoice_id,
                [],
            )
        )

        if len(captures) != 1:
            return False

        capture_id = str(
            captures[0][
                "financial_event_id"
            ]
        )

        if (
            capture_id
            in state.used_event_ids
        ):
            return False

        return (
            invoice[
                "invoice_status"
            ]
            == "PAID"
            and str(
                invoice[
                    "product_id"
                ]
            )
            in product_ids
        )

    invoice = select_first_eligible(
        invoices,
        predicate=eligible,
        label="UNMAPPED_PRODUCT invoice",
    )

    invoice_id = str(
        invoice["invoice_id"]
    )

    capture = (
        invoice_captures[
            invoice_id
        ][0]
    )

    capture_id = str(
        capture[
            "financial_event_id"
        ]
    )

    clean_value = str(
        invoice["product_id"]
    )

    invoice[
        "product_id"
    ] = UNMAPPED_PRODUCT_ID

    state.used_invoice_ids.add(
        invoice_id
    )

    state.used_event_ids.add(
        capture_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "UNMAPPED_PRODUCT"
            ),
            source_table=(
                "raw_billing.invoices"
            ),
            entity_id=invoice_id,
            field_name="product_id",
            clean_value=clean_value,
            anomalous_value=(
                UNMAPPED_PRODUCT_ID
            ),
        )
    )