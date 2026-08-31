from __future__ import annotations

from datetime import UTC, date, datetime


def event(
    event_id: str,
    *,
    invoice_id: str,
    attempt_id: str,
    event_type: str,
    amount_minor: int,
    currency: str = "USD",
    original_capture_id: str | None = None,
    event_day: int = 10,
) -> dict[str, object]:
    return {
        "financial_event_id": event_id,
        "invoice_id": invoice_id,
        "payment_attempt_id": attempt_id,
        "event_type": event_type,
        "amount_minor": amount_minor,
        "currency": currency,
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


def clean_tables() -> dict[
    str,
    list[dict[str, object]],
]:
    invoices = [
        {
            "invoice_id": "INV-001",
            "status": "UNCOLLECTIBLE",
            "currency": "USD",
            "total_amount_minor": 10000,
        },
        {
            "invoice_id": "INV-002",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 10000,
        },
        {
            "invoice_id": "INV-003",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 20000,
        },
        {
            "invoice_id": "INV-004",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 20000,
        },
        {
            "invoice_id": "INV-005",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 50000,
        },
        {
            "invoice_id": "INV-006",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 50000,
        },
        {
            "invoice_id": "INV-007",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 10000,
        },
        {
            "invoice_id": "INV-008",
            "status": "PAID",
            "currency": "USD",
            "total_amount_minor": 40000,
        },
        {
            "invoice_id": "INV-009",
            "status": "PAID",
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
        for number
        in range(
            2,
            10,
        )
    ]

    financial_events = [
        event(
            "EVT-002",
            invoice_id="INV-002",
            attempt_id="ATT-002",
            event_type="CAPTURE",
            amount_minor=10000,
        ),
        event(
            "EVT-003",
            invoice_id="INV-003",
            attempt_id="ATT-003",
            event_type="CAPTURE",
            amount_minor=20000,
        ),
        event(
            "EVT-004",
            invoice_id="INV-004",
            attempt_id="ATT-004",
            event_type="CAPTURE",
            amount_minor=20000,
        ),
        event(
            "EVT-005",
            invoice_id="INV-005",
            attempt_id="ATT-005",
            event_type="CAPTURE",
            amount_minor=50000,
        ),
        event(
            "REF-005",
            invoice_id="INV-005",
            attempt_id="ATT-005",
            event_type="REFUND",
            amount_minor=10000,
            original_capture_id="EVT-005",
        ),
        event(
            "EVT-006",
            invoice_id="INV-006",
            attempt_id="ATT-006",
            event_type="CAPTURE",
            amount_minor=50000,
        ),
        event(
            "REF-006",
            invoice_id="INV-006",
            attempt_id="ATT-006",
            event_type="REFUND",
            amount_minor=30000,
            original_capture_id="EVT-006",
        ),
        event(
            "EVT-007",
            invoice_id="INV-007",
            attempt_id="ATT-007",
            event_type="CAPTURE",
            amount_minor=10000,
        ),
        event(
            "EVT-008",
            invoice_id="INV-008",
            attempt_id="ATT-008",
            event_type="CAPTURE",
            amount_minor=40000,
        ),
        event(
            "EVT-009",
            invoice_id="INV-009",
            attempt_id="ATT-009",
            event_type="CAPTURE",
            amount_minor=60000,
            currency="EUR",
            event_day=10,
        ),
    ]

    settlement_items = [
        {
            "settlement_item_id": (
                f"ITEM-{index:03d}"
            ),
            "settlement_id": (
                "SET-LATE"
                if row[
                    "financial_event_id"
                ]
                == "EVT-009"
                else f"SET-{index:03d}"
            ),
            "financial_event_id": row[
                "financial_event_id"
            ],
        }
        for index, row
        in enumerate(
            financial_events,
            start=1,
        )
    ]

    settlements = [
        {
            "settlement_id": (
                f"SET-{index:03d}"
            ),
            "settlement_date": date(
                2026,
                1,
                11,
            ),
        }
        for index
        in range(
            1,
            len(financial_events)
            + 1,
        )
    ]

    settlements.append(
        {
            "settlement_id": "SET-LATE",
            "settlement_date": date(
                2026,
                1,
                12,
            ),
        }
    )

    return {
        "invoices": invoices,
        "payment_attempts": (
            payment_attempts
        ),
        "financial_events": (
            financial_events
        ),
        "settlement_items": (
            settlement_items
        ),
        "settlements": settlements,
    }