from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    TableRow,
    Tables,
    get_captures,
    get_refunds,
    get_table,
    referenced_capture_ids,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)


def inject_over_refund(
    tables: Tables,
    *,
    state: PaymentLifecycleInjectionState,
) -> None:
    financial_events = get_table(
        tables,
        "financial_events",
    )

    captures = get_captures(
        financial_events
    )

    refunds = get_refunds(
        financial_events
    )

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    selected_pair: tuple[
        TableRow,
        TableRow,
    ] | None = None

    for refund in refunds:
        refund_id = str(
            refund[
                "financial_event_id"
            ]
        )

        if (
            refund_id
            in state.used_event_ids
        ):
            continue

        old_capture_id = str(
            refund[
                "original_capture_id"
            ]
        )

        if (
            old_capture_id
            in state.used_event_ids
        ):
            continue

        for capture in captures:
            capture_id = str(
                capture[
                    "financial_event_id"
                ]
            )

            if (
                capture_id
                in state.used_event_ids
            ):
                continue

            if (
                capture_id
                in referenced_ids
            ):
                continue

            if (
                capture["currency"]
                != refund["currency"]
            ):
                continue

            if (
                int(
                    refund[
                        "amount_minor"
                    ]
                )
                <= int(
                    capture[
                        "amount_minor"
                    ]
                )
            ):
                continue

            selected_pair = (
                refund,
                capture,
            )
            break

        if selected_pair is not None:
            break

    if selected_pair is None:
        raise AnomalySelectionError(
            "No eligible refund/capture "
            "pair for OVER_REFUND"
        )

    refund, target_capture = (
        selected_pair
    )

    refund_id = str(
        refund[
            "financial_event_id"
        ]
    )

    old_capture_id = str(
        refund[
            "original_capture_id"
        ]
    )

    target_capture_id = str(
        target_capture[
            "financial_event_id"
        ]
    )

    refund[
        "original_capture_id"
    ] = target_capture_id

    state.used_event_ids.update(
        {
            refund_id,
            old_capture_id,
            target_capture_id,
        }
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code="OVER_REFUND",
            source_table=(
                "raw_psp.financial_events"
            ),
            entity_id=refund_id,
            field_name=(
                "original_capture_id"
            ),
            clean_value=(
                old_capture_id
            ),
            anomalous_value=(
                target_capture_id
            ),
        )
    )