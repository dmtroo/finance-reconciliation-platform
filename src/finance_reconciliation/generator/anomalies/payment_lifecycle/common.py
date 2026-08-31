from __future__ import annotations

from collections import Counter

from finance_reconciliation.generator.anomalies.common import (
    TableRow,
    TableRows,
    Tables,
    as_date,
    as_datetime,
    get_table,
    row_by_id,
    timestamp_like,
)
from finance_reconciliation.generator.anomalies.selector import (
    AnomalySelectionError,
)


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
        str(
            row[
                "payment_attempt_id"
            ]
        ): row
        for row in payment_attempts
    }


def capture_invoice_id(
    capture: TableRow,
    *,
    attempts_by_id: dict[
        str,
        TableRow,
    ],
) -> str:
    attempt_id = str(
        capture[
            "payment_attempt_id"
        ]
    )

    try:
        attempt = (
            attempts_by_id[
                attempt_id
            ]
        )
    except KeyError as exc:
        raise AnomalySelectionError(
            "Capture references missing "
            "payment attempt: "
            f"{attempt_id}"
        ) from exc

    return str(
        attempt["invoice_id"]
    )


def capture_counts_by_invoice(
    financial_events: TableRows,
    *,
    attempts_by_id: dict[
        str,
        TableRow,
    ],
) -> Counter[str]:
    return Counter(
        capture_invoice_id(
            capture,
            attempts_by_id=(
                attempts_by_id
            ),
        )
        for capture in get_captures(
            financial_events
        )
    )


def captures_by_invoice(
    financial_events: TableRows,
    *,
    attempts_by_id: dict[
        str,
        TableRow,
    ],
) -> dict[str, TableRows]:
    result: dict[
        str,
        TableRows,
    ] = {}

    for capture in get_captures(
        financial_events
    ):
        invoice_id = (
            capture_invoice_id(
                capture,
                attempts_by_id=(
                    attempts_by_id
                ),
            )
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
            event[
                "original_capture_id"
            ]
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
        str(
            item[
                "financial_event_id"
            ]
        )
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
            item[
                "financial_event_id"
            ]
        )

        result.setdefault(
            event_id,
            [],
        ).append(
            item
        )

    return result


__all__ = [
    "TableRow",
    "TableRows",
    "Tables",
    "as_date",
    "as_datetime",
    "capture_counts_by_invoice",
    "capture_invoice_id",
    "captures_by_invoice",
    "get_captures",
    "get_refunds",
    "get_table",
    "payment_attempts_by_id",
    "referenced_capture_ids",
    "row_by_id",
    "settlement_item_counts_by_event",
    "settlement_items_by_event",
    "timestamp_like",
]