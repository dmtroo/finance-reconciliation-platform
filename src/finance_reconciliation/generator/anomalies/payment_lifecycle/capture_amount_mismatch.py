from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    TableRow,
    Tables,
    captures_by_invoice,
    get_table,
    payment_attempts_by_id,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    select_first_eligible,
)

CAPTURE_MISMATCH_DELTA_MINOR = 100


def inject_capture_amount_mismatch(
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

    invoice_captures = (
        captures_by_invoice(
            financial_events,
            attempts_by_id=attempts_by_id,
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

        capture = captures[0]

        return (
            invoice["invoice_status"]
            == "PAID"
            and invoice["currency"]
            == capture["currency"]
            and int(
                invoice[
                    "total_minor"
                ]
            )
            == int(
                capture[
                    "amount_minor"
                ]
            )
        )

    invoice = select_first_eligible(
        invoices,
        predicate=eligible,
        label=(
            "CAPTURE_AMOUNT_MISMATCH "
            "invoice"
        ),
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

    clean_value = int(
        invoice[
            "total_minor"
        ]
    )

    anomalous_value = (
        clean_value
        + CAPTURE_MISMATCH_DELTA_MINOR
    )

    invoice[
        "total_minor"
    ] = anomalous_value

    state.used_invoice_ids.add(
        invoice_id
    )

    state.used_event_ids.add(
        capture_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "CAPTURE_AMOUNT_MISMATCH"
            ),
            source_table=(
                "raw_billing.invoices"
            ),
            entity_id=invoice_id,
            field_name=(
                "total_minor"
            ),
            clean_value=clean_value,
            anomalous_value=(
                anomalous_value
            ),
        )
    )