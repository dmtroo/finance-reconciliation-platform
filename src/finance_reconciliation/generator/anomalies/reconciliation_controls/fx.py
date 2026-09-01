from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from finance_reconciliation.generator.anomalies.common import (
    Tables,
    as_datetime,
    decimal_like,
    get_table,
    timestamp_like,
)
from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    referenced_capture_ids,
    settlement_items_by_event,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)

FX_OUTLIER_MULTIPLIER = Decimal(
    "1.10"
)


def inject_missing_fx_rate(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    financial_events = get_table(
        tables,
        "financial_events",
    )

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    selected = None

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

        if event["currency"] == "EUR":
            continue

        if (
            event_id
            in state.used_event_ids
        ):
            continue

        if event_id in referenced_ids:
            continue

        selected = event
        break

    if selected is None:
        raise AnomalySelectionError(
            "No eligible event for "
            "MISSING_FX_RATE"
        )

    event_id = str(
        selected[
            "financial_event_id"
        ]
    )

    original_value = (
        selected["event_at"]
    )

    original_timestamp = (
        as_datetime(
            original_value
        )
    )

    anomalous_timestamp = datetime(
        2020,
        1,
        1,
        original_timestamp.hour,
        original_timestamp.minute,
        original_timestamp.second,
        tzinfo=(
            original_timestamp.tzinfo
        ),
    )

    selected[
        "event_at"
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
                "MISSING_FX_RATE"
            ),
            source_table=(
                "raw_psp.financial_events"
            ),
            entity_id=event_id,
            field_name=(
                "event_at"
            ),
            clean_value=str(
                original_value
            ),
            anomalous_value=str(
                selected[
                    "event_at"
                ]
            ),
        )
    )


def inject_fx_rate_outlier(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    financial_events = get_table(
        tables,
        "financial_events",
    )

    settlement_items = get_table(
        tables,
        "settlement_items",
    )

    items_by_event = (
        settlement_items_by_event(
            settlement_items
        )
    )

    referenced_ids = (
        referenced_capture_ids(
            financial_events
        )
    )

    selected_event = None
    selected_item = None

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

        if event["currency"] == "EUR":
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

        item = items[0]

        if (
            item.get(
                "psp_fx_rate"
            )
            is None
        ):
            continue

        rate = Decimal(
            str(
                item[
                    "psp_fx_rate"
                ]
            )
        )

        if rate <= 0:
            continue

        selected_event = event
        selected_item = item
        break

    if (
        selected_event is None
        or selected_item is None
    ):
        raise AnomalySelectionError(
            "No eligible event for "
            "FX_RATE_OUTLIER"
        )

    event_id = str(
        selected_event[
            "financial_event_id"
        ]
    )

    original_value = (
        selected_item[
            "psp_fx_rate"
        ]
    )

    original_rate = Decimal(
        str(original_value)
    )

    anomalous_rate = (
        original_rate
        * FX_OUTLIER_MULTIPLIER
    )

    selected_item[
        "psp_fx_rate"
    ] = decimal_like(
        original_value,
        anomalous_rate,
    )

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "FX_RATE_OUTLIER"
            ),
            source_table=(
                "raw_psp.settlement_items"
            ),
            entity_id=event_id,
            field_name="psp_fx_rate",
            clean_value=str(
                original_rate
            ),
            anomalous_value=str(
                anomalous_rate
            ),
        )
    )