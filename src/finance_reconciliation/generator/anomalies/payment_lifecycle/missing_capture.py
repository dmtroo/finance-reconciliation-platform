from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    Tables,
    capture_counts_by_invoice,
    get_table,
    payment_attempts_by_id,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    select_first_eligible,
)


def inject_missing_capture(
    tables: Tables,
    *,
    state: PaymentLifecycleInjectionState,
) -> None:
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

    attempts_by_id = (
        payment_attempts_by_id(
            payment_attempts
        )
    )

    capture_counts = (
        capture_counts_by_invoice(
            financial_events,
            attempts_by_id=attempts_by_id,
        )
    )

    invoice = select_first_eligible(
        invoices,
        predicate=lambda row: (
            str(row["invoice_id"])
            not in state.used_invoice_ids
            and row["invoice_status"]
            == "UNCOLLECTIBLE"
            and capture_counts.get(
                str(row["invoice_id"]),
                0,
            )
            == 0
        ),
        label="MISSING_CAPTURE invoice",
    )

    invoice_id = str(
        invoice["invoice_id"]
    )

    clean_value = (
        invoice["invoice_status"]
    )

    invoice[
        "invoice_status"
    ] = "PAID"

    state.used_invoice_ids.add(
        invoice_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code="MISSING_CAPTURE",
            source_table=(
                "raw_billing.invoices"
            ),
            entity_id=invoice_id,
            field_name="invoice_status",
            clean_value=clean_value,
            anomalous_value="PAID",
        )
    )