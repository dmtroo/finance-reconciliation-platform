from __future__ import annotations

from datetime import (
    UTC,
    date,
    datetime,
)

import pytest


def financial_event(
    event_id: str,
    *,
    attempt_id: str,
    event_type: str,
    amount_minor: int,
    currency: str = "USD",
    original_capture_id: (
        str | None
    ) = None,
    event_day: int = 10,
) -> dict[str, object]:
    return {
        "financial_event_id": (
            event_id
        ),
        "payment_attempt_id": (
            attempt_id
        ),
        "event_type": (
            event_type
        ),
        "amount_minor": (
            amount_minor
        ),
        "currency": (
            currency
        ),
        "original_capture_id": (
            original_capture_id
        ),
        "event_timestamp": datetime(
            2026,
            1,
            event_day,
            12,
            0,
            tzinfo=UTC,
        ),
    }


@pytest.fixture
def clean_lifecycle_tables() -> dict[
    str,
    list[dict[str, object]],
]:
    invoices = [
    {
        "invoice_id": "INV-001",
        "invoice_status": "UNCOLLECTIBLE",
        "currency": "USD",
        "total_amount_minor": 10000,
    },
    {
        "invoice_id": "INV-002",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 10000,
    },
    {
        "invoice_id": "INV-003",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 20000,
    },
    {
        "invoice_id": "INV-004",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 20000,
    },
    {
        "invoice_id": "INV-005",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 50000,
    },
    {
        "invoice_id": "INV-006",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 50000,
    },
    {
        "invoice_id": "INV-007",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 10000,
    },
    {
        "invoice_id": "INV-008",
        "invoice_status": "PAID",
        "currency": "USD",
        "total_amount_minor": 40000,
    },
    {
        "invoice_id": "INV-009",
        "invoice_status": "PAID",
        "currency": "EUR",
        "total_amount_minor": 60000,
    },
]

    payment_attempts = [
        {
            "payment_attempt_id": (
                f"ATT-{number:03d}"
            ),
            "invoice_id": (
                f"INV-{number:03d}"
            ),
            "status": "SUCCEEDED",
        }
        for number in range(
            2,
            10,
        )
    ]

    events = [
        financial_event(
            "EVT-002",
            attempt_id="ATT-002",
            event_type="CAPTURE",
            amount_minor=10000,
        ),
        financial_event(
            "EVT-003",
            attempt_id="ATT-003",
            event_type="CAPTURE",
            amount_minor=20000,
        ),
        financial_event(
            "EVT-004",
            attempt_id="ATT-004",
            event_type="CAPTURE",
            amount_minor=20000,
        ),
        financial_event(
            "EVT-005",
            attempt_id="ATT-005",
            event_type="CAPTURE",
            amount_minor=50000,
        ),
        financial_event(
            "REF-005",
            attempt_id="ATT-005",
            event_type="REFUND",
            amount_minor=10000,
            original_capture_id=(
                "EVT-005"
            ),
        ),
        financial_event(
            "EVT-006",
            attempt_id="ATT-006",
            event_type="CAPTURE",
            amount_minor=50000,
        ),
        financial_event(
            "REF-006",
            attempt_id="ATT-006",
            event_type="REFUND",
            amount_minor=30000,
            original_capture_id=(
                "EVT-006"
            ),
        ),
        financial_event(
            "EVT-007",
            attempt_id="ATT-007",
            event_type="CAPTURE",
            amount_minor=10000,
        ),
        financial_event(
            "EVT-008",
            attempt_id="ATT-008",
            event_type="CAPTURE",
            amount_minor=40000,
        ),
        financial_event(
            "EVT-009",
            attempt_id="ATT-009",
            event_type="CAPTURE",
            amount_minor=60000,
            currency="EUR",
        ),
    ]

    settlement_items: list[
        dict[str, object]
    ] = []

    settlements: list[
        dict[str, object]
    ] = []

    for index, event in enumerate(
        events,
        start=1,
    ):
        event_id = str(
            event[
                "financial_event_id"
            ]
        )

        if event_id == "EVT-009":
            settlement_id = (
                "SET-LATE"
            )

            settlement_date = date(
                2026,
                1,
                12,
            )
        else:
            settlement_id = (
                f"SET-{index:03d}"
            )

            settlement_date = date(
                2026,
                1,
                11,
            )

        settlement_items.append(
            {
                "settlement_item_id": (
                    f"ITEM-{index:03d}"
                ),
                "settlement_id": (
                    settlement_id
                ),
                "financial_event_id": (
                    event_id
                ),
            }
        )

        settlements.append(
            {
                "settlement_id": (
                    settlement_id
                ),
                "settlement_date": (
                    settlement_date
                ),
            }
        )

    return {
        "invoices": invoices,
        "payment_attempts": (
            payment_attempts
        ),
        "financial_events": events,
        "settlement_items": (
            settlement_items
        ),
        "settlements": settlements,
    }