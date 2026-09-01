from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    TableRow,
    TableRows,
)


def events_by_id(
    financial_events: TableRows,
) -> dict[str, TableRow]:
    return {
        str(
            event[
                "financial_event_id"
            ]
        ): event
        for event in financial_events
    }


def settlement_items_by_settlement(
    settlement_items: TableRows,
) -> dict[str, TableRows]:
    result: dict[
        str,
        TableRows,
    ] = {}

    for item in settlement_items:
        settlement_id = str(
            item["settlement_id"]
        )

        result.setdefault(
            settlement_id,
            [],
        ).append(
            item
        )

    return result


def event_ids_for_settlement(
    settlement_id: str,
    *,
    items_by_settlement: dict[
        str,
        TableRows,
    ],
) -> set[str]:
    return {
        str(
            item[
                "financial_event_id"
            ]
        )
        for item
        in items_by_settlement.get(
            settlement_id,
            [],
        )
    }


def journal_lines_by_entry(
    journal_lines: TableRows,
) -> dict[str, TableRows]:
    result: dict[
        str,
        TableRows,
    ] = {}

    for line in journal_lines:
        journal_entry_id = str(
            line["journal_entry_id"]
        )

        result.setdefault(
            journal_entry_id,
            [],
        ).append(
            line
        )

    return result