from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)

TableRow = dict[str, Any]
TableRows = list[TableRow]
Tables = dict[str, TableRows]


def get_table(
    tables: Tables,
    name: str,
) -> TableRows:
    try:
        return tables[name]
    except KeyError as exc:
        raise AnomalySelectionError(
            f"Missing generated table: {name}"
        ) from exc


def get_captures(
    financial_events: TableRows,
) -> TableRows:
    return [
        row
        for row in financial_events
        if row["event_type"] == "CAPTURE"
    ]


def get_refunds(
    financial_events: TableRows,
) -> TableRows:
    return [
        row
        for row in financial_events
        if row["event_type"] == "REFUND"
    ]


def payment_attempts_by_id(
    payment_attempts: TableRows,
) -> dict[str, TableRow]:
    return {
        str(row["payment_attempt_id"]): row
        for row in payment_attempts
    }


def capture_invoice_id(
    capture: TableRow,
    *,
    attempts_by_id: dict[str, TableRow],
) -> str:
    attempt_id = str(
        capture["payment_attempt_id"]
    )

    try:
        attempt = attempts_by_id[
            attempt_id
        ]
    except KeyError as exc:
        raise AnomalySelectionError(
            "Capture references missing "
            f"payment attempt: {attempt_id}"
        ) from exc

    return str(
        attempt["invoice_id"]
    )


def capture_counts_by_invoice(
    financial_events: TableRows,
    *,
    attempts_by_id: dict[str, TableRow],
) -> Counter[str]:
    return Counter(
        capture_invoice_id(
            capture,
            attempts_by_id=attempts_by_id,
        )
        for capture in get_captures(
            financial_events
        )
    )


def captures_by_invoice(
    financial_events: TableRows,
    *,
    attempts_by_id: dict[str, TableRow],
) -> dict[str, TableRows]:
    result: dict[
        str,
        TableRows,
    ] = {}

    for capture in get_captures(
        financial_events
    ):
        invoice_id = capture_invoice_id(
            capture,
            attempts_by_id=attempts_by_id,
        )

        result.setdefault(
            invoice_id,
            [],
        ).append(
            capture
        )

    return result


def referenced_capture_ids(
    financial_events: TableRows,
) -> set[str]:
    return {
        str(
            event["original_capture_id"]
        )
        for event in financial_events
        if (
            event["event_type"]
            in {
                "REFUND",
                "CHARGEBACK",
            }
            and event[
                "original_capture_id"
            ]
            is not None
        )
    }


def settlement_item_counts_by_event(
    settlement_items: TableRows,
) -> Counter[str]:
    return Counter(
        str(item["financial_event_id"])
        for item in settlement_items
    )


def settlement_items_by_event(
    settlement_items: TableRows,
) -> dict[str, TableRows]:
    result: dict[
        str,
        TableRows,
    ] = {}

    for item in settlement_items:
        event_id = str(
            item["financial_event_id"]
        )

        result.setdefault(
            event_id,
            [],
        ).append(
            item
        )

    return result


def row_by_id(
    rows: TableRows,
    *,
    id_field: str,
    entity_id: str,
) -> TableRow:
    for row in rows:
        if (
            str(row[id_field])
            == entity_id
        ):
            return row

    raise AnomalySelectionError(
        f"Could not find "
        f"{id_field}={entity_id}"
    )


def as_date(
    value: Any,
) -> date:
    if isinstance(
        value,
        datetime,
    ):
        return value.date()

    if isinstance(
        value,
        date,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return date.fromisoformat(
            value[:10]
        )

    raise TypeError(
        f"Cannot convert "
        f"{value!r} to date"
    )


def as_datetime(
    value: Any,
) -> datetime:
    if isinstance(
        value,
        datetime,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return datetime.fromisoformat(value)

    raise TypeError(
        f"Cannot convert "
        f"{value!r} to datetime"
    )


def timestamp_like(
    original: Any,
    value: datetime,
) -> Any:
    if isinstance(
        original,
        str,
    ):
        return value.isoformat()

    return value