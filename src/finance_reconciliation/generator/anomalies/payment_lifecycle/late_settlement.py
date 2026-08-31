from __future__ import annotations

from datetime import timedelta

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    TableRow,
    Tables,
    as_date,
    as_datetime,
    get_table,
    referenced_capture_ids,
    settlement_items_by_event,
    timestamp_like,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.state import (
    PaymentLifecycleInjectionState,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)

LATE_SETTLEMENT_DELAY_DAYS = 6


def inject_late_settlement(
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

    settlements = get_table(
        tables,
        "settlements",
    )

    items_by_event = (
        settlement_items_by_event(
            settlement_items
        )
    )

    settlements_by_id = {
        str(
            row["settlement_id"]
        ): row
        for row in settlements
    }

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    selected: tuple[
        TableRow,
        TableRow,
    ] | None = None

    for event in financial_events:
        event_id = str(
            event[
                "financial_event_id"
            ]
        )

        if (
            event["event_type"]
            != "CAPTURE"
        ):
            continue

        if event["currency"] != "EUR":
            continue

        if (
            event_id
            in state.used_event_ids
        ):
            continue

        if event_id in referenced_ids:
            continue

        items = items_by_event.get(
            event_id,
            [],
        )

        if len(items) != 1:
            continue

        settlement_id = str(
            items[0][
                "settlement_id"
            ]
        )

        settlement = (
            settlements_by_id.get(
                settlement_id
            )
        )

        if settlement is None:
            continue

        event_date = as_date(
            event[
                "event_timestamp"
            ]
        )

        settlement_date = as_date(
            settlement[
                "settlement_date"
            ]
        )

        current_delay = (
            settlement_date
            - event_date
        ).days

        if (
            0
            <= current_delay
            <= 5
        ):
            selected = (
                event,
                settlement,
            )
            break

    if selected is None:
        raise AnomalySelectionError(
            "No eligible EUR capture "
            "for LATE_SETTLEMENT"
        )

    event, settlement = selected

    event_id = str(
        event[
            "financial_event_id"
        ]
    )

    original_value = (
        event["event_timestamp"]
    )

    original_timestamp = (
        as_datetime(
            original_value
        )
    )

    settlement_date = as_date(
        settlement[
            "settlement_date"
        ]
    )

    current_delay = (
        settlement_date
        - original_timestamp.date()
    ).days

    shift_days = (
        LATE_SETTLEMENT_DELAY_DAYS
        - current_delay
    )

    anomalous_timestamp = (
        original_timestamp
        - timedelta(
            days=shift_days
        )
    )

    event[
        "event_timestamp"
    ] = timestamp_like(
        original_value,
        anomalous_timestamp,
    )

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "LATE_SETTLEMENT"
            ),
            source_table=(
                "raw_psp.financial_events"
            ),
            entity_id=event_id,
            field_name=(
                "event_timestamp"
            ),
            clean_value=str(
                original_value
            ),
            anomalous_value=str(
                event[
                    "event_timestamp"
                ]
            ),
        )
    )