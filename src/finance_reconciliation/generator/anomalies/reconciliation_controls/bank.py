from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    TableRow,
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

BANK_MISMATCH_DELTA_MINOR = 100


def _eligible_settlement_and_bank_row(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> tuple[
    TableRow,
    TableRow,
    set[str],
]:
    settlements = get_table(
        tables,
        "settlements",
    )

    settlement_items = get_table(
        tables,
        "settlement_items",
    )

    bank_transactions = get_table(
        tables,
        "statement_transactions",
    )

    items_by_settlement = (
        settlement_items_by_settlement(
            settlement_items
        )
    )

    for settlement in settlements:
        settlement_id = str(
            settlement["settlement_id"]
        )

        if (
            settlement_id
            in state.used_settlement_ids
        ):
            continue

        event_ids = (
            event_ids_for_settlement(
                settlement_id,
                items_by_settlement=(
                    items_by_settlement
                ),
            )
        )

        if not event_ids:
            continue

        if (
            event_ids
            & state.used_event_ids
        ):
            continue

        bank_reference = str(
            settlement[
                "bank_reference"
            ]
        )

        matching_rows = [
            row
            for row in bank_transactions
            if str(
                row[
                    "payment_reference"
                ]
            )
            == bank_reference
        ]

        if len(matching_rows) != 1:
            continue

        return (
            settlement,
            matching_rows[0],
            event_ids,
        )

    raise AnomalySelectionError(
        "No eligible settlement/bank "
        "pair"
    )


def inject_missing_bank_receipt(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    (
        settlement,
        _bank_row,
        event_ids,
    ) = _eligible_settlement_and_bank_row(
        tables,
        state=state,
    )

    settlement_id = str(
        settlement["settlement_id"]
    )

    clean_value = str(
        settlement[
            "bank_reference"
        ]
    )

    anomalous_value = (
        f"BANK-MISSING-{settlement_id}"
    )

    settlement[
        "bank_reference"
    ] = anomalous_value

    state.used_settlement_ids.add(
        settlement_id
    )

    state.used_event_ids.update(
        event_ids
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "MISSING_BANK_RECEIPT"
            ),
            source_table=(
                "raw_psp.settlements"
            ),
            entity_id=settlement_id,
            field_name=(
                "bank_reference"
            ),
            clean_value=clean_value,
            anomalous_value=(
                anomalous_value
            ),
        )
    )


def inject_bank_amount_mismatch(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    (
        settlement,
        bank_row,
        event_ids,
    ) = _eligible_settlement_and_bank_row(
        tables,
        state=state,
    )

    settlement_id = str(
        settlement["settlement_id"]
    )

    clean_value = int(
        bank_row[
            "amount_minor"
        ]
    )

    anomalous_value = (
        clean_value
        + BANK_MISMATCH_DELTA_MINOR
    )

    bank_row[
        "amount_minor"
    ] = anomalous_value

    state.used_settlement_ids.add(
        settlement_id
    )

    state.used_event_ids.update(
        event_ids
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "BANK_AMOUNT_MISMATCH"
            ),
            source_table=(
                "raw_bank."
                "statement_transactions"
            ),
            entity_id=settlement_id,
            field_name="amount_minor",
            clean_value=clean_value,
            anomalous_value=(
                anomalous_value
            ),
        )
    )