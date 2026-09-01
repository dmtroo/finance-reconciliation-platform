from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    Tables,
    get_table,
)
from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.common import (
    event_ids_for_settlement,
    settlement_items_by_settlement,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)

SETTLEMENT_MISMATCH_DELTA_MINOR = 100


def inject_settlement_total_mismatch(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    settlements = get_table(
        tables,
        "settlements",
    )

    settlement_items = get_table(
        tables,
        "settlement_items",
    )

    items_by_settlement = (
        settlement_items_by_settlement(
            settlement_items
        )
    )

    selected_settlement = None

    for settlement in settlements:
        settlement_id = str(
            settlement["settlement_id"]
        )

        if (
            settlement_id
            in state.used_settlement_ids
        ):
            continue

        items = (
            items_by_settlement.get(
                settlement_id,
                [],
            )
        )

        if not items:
            continue

        event_ids = (
            event_ids_for_settlement(
                settlement_id,
                items_by_settlement=(
                    items_by_settlement
                ),
            )
        )

        if (
            event_ids
            & state.used_event_ids
        ):
            continue

        selected_settlement = (
            settlement
        )
        break

    if selected_settlement is None:
        raise AnomalySelectionError(
            "No eligible settlement for "
            "SETTLEMENT_TOTAL_MISMATCH"
        )

    settlement_id = str(
        selected_settlement[
            "settlement_id"
        ]
    )

    items = (
        items_by_settlement[
            settlement_id
        ]
    )

    target_item = items[0]

    clean_value = int(
        target_item[
            "settlement_gross_eur_minor"
        ]
    )

    anomalous_value = (
        clean_value
        + SETTLEMENT_MISMATCH_DELTA_MINOR
    )

    target_item[
        "settlement_gross_eur_minor"
    ] = anomalous_value

    event_ids = (
        event_ids_for_settlement(
            settlement_id,
            items_by_settlement=(
                items_by_settlement
            ),
        )
    )

    state.used_settlement_ids.add(
        settlement_id
    )

    state.used_event_ids.update(
        event_ids
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "SETTLEMENT_TOTAL_MISMATCH"
            ),
            source_table=(
                "raw_psp.settlement_items"
            ),
            entity_id=settlement_id,
            field_name=(
                "settlement_gross_eur_minor"
            ),
            clean_value=clean_value,
            anomalous_value=(
                anomalous_value
            ),
        )
    )