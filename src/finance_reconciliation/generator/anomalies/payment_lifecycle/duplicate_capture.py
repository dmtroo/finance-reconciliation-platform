from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    TableRow,
    Tables,
    capture_counts_by_invoice,
    capture_invoice_id,
    get_captures,
    get_table,
    payment_attempts_by_id,
    referenced_capture_ids,
    row_by_id,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)


def inject_duplicate_capture(
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

    invoices_by_id = {
        str(row["invoice_id"]): row
        for row in invoices
    }

    capture_counts = (
        capture_counts_by_invoice(
            financial_events,
            attempts_by_id=attempts_by_id,
        )
    )

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    eligible_captures: list[
        TableRow
    ] = []

    for capture in get_captures(
        financial_events
    ):
        capture_id = str(
            capture[
                "financial_event_id"
            ]
        )

        invoice_id = (
            capture_invoice_id(
                capture,
                attempts_by_id=attempts_by_id,
            )
        )

        if (
            capture_id
            in state.used_event_ids
        ):
            continue

        if (
            invoice_id
            in state.used_invoice_ids
        ):
            continue

        if (
            capture_id
            in referenced_ids
        ):
            continue

        if (
            capture_counts.get(
                invoice_id,
                0,
            )
            != 1
        ):
            continue

        if (
            invoices_by_id[
                invoice_id
            ]["invoice_status"]
            != "PAID"
        ):
            continue

        eligible_captures.append(
            capture
        )

    selected_pair: tuple[
        TableRow,
        TableRow,
    ] | None = None

    for target in eligible_captures:
        for donor in eligible_captures:
            if donor is target:
                continue

            if (
                donor["currency"]
                != target["currency"]
            ):
                continue

            if (
                int(
                    donor[
                        "amount_minor"
                    ]
                )
                != int(
                    target[
                        "amount_minor"
                    ]
                )
            ):
                continue

            selected_pair = (
                target,
                donor,
            )
            break

        if selected_pair is not None:
            break

    if selected_pair is None:
        raise AnomalySelectionError(
            "No eligible equal-value "
            "capture pair for "
            "DUPLICATE_CAPTURE"
        )

    target_capture, donor_capture = (
        selected_pair
    )

    target_capture_id = str(
        target_capture[
            "financial_event_id"
        ]
    )

    donor_capture_id = str(
        donor_capture[
            "financial_event_id"
        ]
    )

    target_invoice_id = (
        capture_invoice_id(
            target_capture,
            attempts_by_id=attempts_by_id,
        )
    )

    donor_invoice_id = (
        capture_invoice_id(
            donor_capture,
            attempts_by_id=attempts_by_id,
        )
    )

    target_attempt_id = str(
        target_capture[
            "payment_attempt_id"
        ]
    )

    donor_attempt_id = str(
        donor_capture[
            "payment_attempt_id"
        ]
    )

    donor_attempt = row_by_id(
        payment_attempts,
        id_field=(
            "payment_attempt_id"
        ),
        entity_id=donor_attempt_id,
    )

    donor_invoice = (
        invoices_by_id[
            donor_invoice_id
        ]
    )

    donor_capture[
        "payment_attempt_id"
    ] = target_attempt_id

    # The reconciliation marts resolve a capture's invoice from
    # financial_events.invoice_id directly, not through the payment
    # attempt, so the donor capture must also carry the target
    # invoice_id for the duplicate to surface as an exception.
    donor_capture[
        "invoice_id"
    ] = target_invoice_id

    donor_attempt[
        "status"
    ] = "DECLINED"

    donor_invoice[
        "invoice_status"
    ] = "UNCOLLECTIBLE"

    state.used_invoice_ids.update(
        {
            target_invoice_id,
            donor_invoice_id,
        }
    )

    state.used_event_ids.update(
        {
            target_capture_id,
            donor_capture_id,
        }
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "DUPLICATE_CAPTURE"
            ),
            source_table=(
                "raw_psp.financial_events"
            ),
            entity_id=(
                donor_capture_id
            ),
            field_name=(
                "payment_attempt_id"
            ),
            clean_value=(
                donor_attempt_id
            ),
            anomalous_value=(
                target_attempt_id
            ),
        )
    )