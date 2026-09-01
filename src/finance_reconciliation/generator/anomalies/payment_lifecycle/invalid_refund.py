from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    Tables,
    get_captures,
    get_table,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    select_first_eligible,
)

MISSING_CAPTURE_ID = (
    "EVT-MISSING-ORIGINAL-CAPTURE"
)


def inject_invalid_refund(
    tables: Tables,
    *,
    state: PaymentLifecycleInjectionState,
) -> None:
    financial_events = get_table(
        tables,
        "financial_events",
    )

    capture_ids = {
        str(
            capture[
                "financial_event_id"
            ]
        )
        for capture in get_captures(
            financial_events
        )
    }

    refund = select_first_eligible(
        financial_events,
        predicate=lambda row: (
            row["event_type"] == "REFUND"
            and str(
                row[
                    "financial_event_id"
                ]
            )
            not in state.used_event_ids
            and row[
                "original_capture_id"
            ]
            is not None
            and str(
                row[
                    "original_capture_id"
                ]
            )
            in capture_ids
            and str(
                row[
                    "original_capture_id"
                ]
            )
            not in state.used_event_ids
        ),
        label="INVALID_REFUND event",
    )

    refund_id = str(
        refund[
            "financial_event_id"
        ]
    )

    original_capture_id = str(
        refund[
            "original_capture_id"
        ]
    )

    refund[
        "original_capture_id"
    ] = MISSING_CAPTURE_ID

    state.used_event_ids.update(
        {
            refund_id,
            original_capture_id,
        }
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "INVALID_REFUND"
            ),
            source_table=(
                "raw_psp.financial_events"
            ),
            entity_id=refund_id,
            field_name=(
                "original_capture_id"
            ),
            clean_value=(
                original_capture_id
            ),
            anomalous_value=(
                MISSING_CAPTURE_ID
            ),
        )
    )