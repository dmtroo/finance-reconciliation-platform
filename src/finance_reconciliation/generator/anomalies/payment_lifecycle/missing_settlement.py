from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    Tables,
    get_table,
    referenced_capture_ids,
    settlement_item_counts_by_event,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    select_first_eligible,
)


def inject_missing_settlement(
    tables: Tables,
    *,
    state: PaymentLifecycleInjectionState,
) -> None:
    financial_events = get_table(
        tables,
        "financial_events",
    )

    settlement_items = get_table(
        tables,
        "settlement_items",
    )

    item_counts = (
        settlement_item_counts_by_event(
            settlement_items
        )
    )

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    event = select_first_eligible(
        financial_events,
        predicate=lambda row: (
            row["event_type"] == "CAPTURE"
            and str(
                row[
                    "financial_event_id"
                ]
            )
            not in state.used_event_ids
            and str(
                row[
                    "financial_event_id"
                ]
            )
            not in referenced_ids
            and item_counts.get(
                str(
                    row[
                        "financial_event_id"
                    ]
                ),
                0,
            )
            == 1
        ),
        label=(
            "MISSING_SETTLEMENT event"
        ),
    )

    event_id = str(
        event[
            "financial_event_id"
        ]
    )

    settlement_item = next(
        item
        for item in settlement_items
        if str(
            item[
                "financial_event_id"
            ]
        )
        == event_id
    )

    orphaned_reference = (
        f"EVT-ORPHANED-{event_id}"
    )

    settlement_item[
        "financial_event_id"
    ] = orphaned_reference

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "MISSING_SETTLEMENT"
            ),
            source_table=(
                "raw_psp.settlement_items"
            ),
            entity_id=event_id,
            field_name=(
                "financial_event_id"
            ),
            clean_value=event_id,
            anomalous_value=(
                orphaned_reference
            ),
        )
    )