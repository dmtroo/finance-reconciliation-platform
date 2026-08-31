from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    TableRows,
    Tables,
    get_table,
)
from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.common import (
    journal_lines_by_entry,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)

LEDGER_MISMATCH_DELTA_MINOR = 100
UNBALANCED_DELTA_MINOR = 100


def _eligible_event_journal_entry(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> tuple[
    str,
    str,
    TableRows,
]:
    journal_lines = get_table(
        tables,
        "journal_lines",
    )

    lines_by_entry = (
        journal_lines_by_entry(
            journal_lines
        )
    )

    for (
        journal_entry_id,
        lines,
    ) in lines_by_entry.items():
        if (
            journal_entry_id
            in state.used_journal_entry_ids
        ):
            continue

        source_types = {
            str(
                line[
                    "source_reference_type"
                ]
            )
            for line in lines
        }

        references = {
            str(
                line[
                    "source_reference"
                ]
            )
            for line in lines
        }

        if source_types != {
            "FINANCIAL_EVENT"
        }:
            continue

        if len(references) != 1:
            continue

        event_id = next(
            iter(references)
        )

        if (
            event_id
            in state.used_event_ids
        ):
            continue

        debit_lines = [
            line
            for line in lines
            if int(
                line[
                    "debit_amount_minor"
                ]
            )
            > 0
        ]

        credit_lines = [
            line
            for line in lines
            if int(
                line[
                    "credit_amount_minor"
                ]
            )
            > 0
        ]

        if len(debit_lines) != 1:
            continue

        if len(credit_lines) != 1:
            continue

        return (
            journal_entry_id,
            event_id,
            lines,
        )

    raise AnomalySelectionError(
        "No eligible financial-event "
        "journal entry"
    )


def inject_missing_ledger_posting(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    (
        journal_entry_id,
        event_id,
        lines,
    ) = _eligible_event_journal_entry(
        tables,
        state=state,
    )

    anomalous_reference = (
        f"EVT-ORPHANED-LEDGER-"
        f"{event_id}"
    )

    for line in lines:
        line[
            "source_reference"
        ] = anomalous_reference

    state.used_journal_entry_ids.add(
        journal_entry_id
    )

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "MISSING_LEDGER_POSTING"
            ),
            source_table=(
                "raw_accounting.journal_lines"
            ),
            entity_id=event_id,
            field_name=(
                "source_reference"
            ),
            clean_value=event_id,
            anomalous_value=(
                anomalous_reference
            ),
        )
    )


def inject_ledger_amount_mismatch(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    (
        journal_entry_id,
        event_id,
        lines,
    ) = _eligible_event_journal_entry(
        tables,
        state=state,
    )

    clean_debit = sum(
        int(
            line[
                "debit_amount_minor"
            ]
        )
        for line in lines
    )

    clean_credit = sum(
        int(
            line[
                "credit_amount_minor"
            ]
        )
        for line in lines
    )

    for line in lines:
        debit = int(
            line[
                "debit_amount_minor"
            ]
        )

        credit = int(
            line[
                "credit_amount_minor"
            ]
        )

        if debit > 0:
            line[
                "debit_amount_minor"
            ] = (
                debit
                + LEDGER_MISMATCH_DELTA_MINOR
            )

        if credit > 0:
            line[
                "credit_amount_minor"
            ] = (
                credit
                + LEDGER_MISMATCH_DELTA_MINOR
            )

    anomalous_debit = sum(
        int(
            line[
                "debit_amount_minor"
            ]
        )
        for line in lines
    )

    anomalous_credit = sum(
        int(
            line[
                "credit_amount_minor"
            ]
        )
        for line in lines
    )

    state.used_journal_entry_ids.add(
        journal_entry_id
    )

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "LEDGER_AMOUNT_MISMATCH"
            ),
            source_table=(
                "raw_accounting.journal_lines"
            ),
            entity_id=event_id,
            field_name=(
                "journal_entry_amounts_minor"
            ),
            clean_value={
                "debit": clean_debit,
                "credit": clean_credit,
            },
            anomalous_value={
                "debit": anomalous_debit,
                "credit": anomalous_credit,
            },
        )
    )


def inject_unbalanced_journal(
    tables: Tables,
    *,
    state: AnomalyInjectionState,
) -> None:
    (
        journal_entry_id,
        event_id,
        lines,
    ) = _eligible_event_journal_entry(
        tables,
        state=state,
    )

    debit_line = next(
        line
        for line in lines
        if int(
            line[
                "debit_amount_minor"
            ]
        )
        > 0
    )

    clean_value = int(
        debit_line[
            "debit_amount_minor"
        ]
    )

    anomalous_value = (
        clean_value
        + UNBALANCED_DELTA_MINOR
    )

    debit_line[
        "debit_amount_minor"
    ] = anomalous_value

    state.used_journal_entry_ids.add(
        journal_entry_id
    )

    state.used_event_ids.add(
        event_id
    )

    state.anomalies.append(
        AnomalyRecord(
            anomaly_code=(
                "UNBALANCED_JOURNAL"
            ),
            source_table=(
                "raw_accounting.journal_lines"
            ),
            entity_id=event_id,
            field_name=(
                "debit_amount_minor"
            ),
            clean_value=clean_value,
            anomalous_value=(
                anomalous_value
            ),
        )
    )