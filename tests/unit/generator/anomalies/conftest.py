from __future__ import annotations

from datetime import (
    UTC,
    date,
    datetime,
)
from decimal import Decimal

import pytest

CAPTURE_AMOUNTS = {
    2: 10000,
    3: 20000,
    4: 20000,
    5: 50000,
    6: 50000,
    7: 10000,
    8: 40000,
    9: 60000,
    10: 70000,
    11: 80000,
    12: 90000,
    13: 110000,
    14: 120000,
    15: 130000,
    16: 140000,
    17: 150000,
    18: 160000,
    19: 170000,
}


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
    invoice_id: str | None = None,
    event_day: int = 10,
) -> dict[str, object]:
    return {
        "financial_event_id": (
            event_id
        ),
        "payment_attempt_id": (
            attempt_id
        ),
        "invoice_id": (
            invoice_id
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
        "event_at": datetime(
            2026,
            1,
            event_day,
            12,
            0,
            tzinfo=UTC,
        ),
    }


def accounting_entry(
    *,
    journal_entry_id: str,
    source_reference_type: str,
    source_reference: str,
    debit_account: str,
    credit_account: str,
    amount_minor: int,
) -> list[dict[str, object]]:
    return [
        {
            "journal_line_id": (
                f"{journal_entry_id}-01"
            ),
            "journal_entry_id": (
                journal_entry_id
            ),
            "account_code": (
                debit_account
            ),
            "debit_eur_minor": (
                amount_minor
            ),
            "credit_eur_minor": 0,
            "source_reference_type": (
                source_reference_type
            ),
            "source_reference": (
                source_reference
            ),
        },
        {
            "journal_line_id": (
                f"{journal_entry_id}-02"
            ),
            "journal_entry_id": (
                journal_entry_id
            ),
            "account_code": (
                credit_account
            ),
            "debit_eur_minor": 0,
            "credit_eur_minor": (
                amount_minor
            ),
            "source_reference_type": (
                source_reference_type
            ),
            "source_reference": (
                source_reference
            ),
        },
    ]


@pytest.fixture
def clean_lifecycle_tables() -> dict[
    str,
    list[dict[str, object]],
]:
    products = [
        {
            "product_id": "PROD-001",
        },
        {
            "product_id": "PROD-002",
        },
    ]

    invoices: list[
        dict[str, object]
    ] = [
        {
            "invoice_id": "INV-001",
            "invoice_status": (
                "UNCOLLECTIBLE"
            ),
            "currency": "USD",
            "product_id": "PROD-001",
            "total_amount_minor": 10000,
        }
    ]

    for number in range(
        2,
        20,
    ):
        currency = (
            "EUR"
            if number == 9
            else "USD"
        )

        invoices.append(
            {
                "invoice_id": (
                    f"INV-{number:03d}"
                ),
                "invoice_status": "PAID",
                "currency": currency,
                "product_id": (
                    "PROD-001"
                ),
                "total_minor": (
                    CAPTURE_AMOUNTS[
                        number
                    ]
                ),
            }
        )

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
            20,
        )
    ]

    financial_events = [
        financial_event(
            f"EVT-{number:03d}",
            attempt_id=(
                f"ATT-{number:03d}"
            ),
            invoice_id=(
                f"INV-{number:03d}"
            ),
            event_type="CAPTURE",
            amount_minor=(
                CAPTURE_AMOUNTS[
                    number
                ]
            ),
            currency=(
                "EUR"
                if number == 9
                else "USD"
            ),
        )
        for number
        in range(
            2,
            20,
        )
    ]

    financial_events.extend(
        [
            financial_event(
                "REF-005",
                attempt_id="ATT-005",
                invoice_id="INV-005",
                event_type="REFUND",
                amount_minor=10000,
                original_capture_id=(
                    "EVT-005"
                ),
            ),
            financial_event(
                "REF-006",
                attempt_id="ATT-006",
                invoice_id="INV-006",
                event_type="REFUND",
                amount_minor=30000,
                original_capture_id=(
                    "EVT-006"
                ),
            ),
        ]
    )

    settlement_items: list[
        dict[str, object]
    ] = []

    settlements: list[
        dict[str, object]
    ] = []

    statement_transactions: list[
        dict[str, object]
    ] = []

    journal_lines: list[
        dict[str, object]
    ] = []

    for index, event in enumerate(
        financial_events,
        start=1,
    ):
        event_id = str(
            event[
                "financial_event_id"
            ]
        )

        gross_amount_minor = int(
            event["amount_minor"]
        )

        fee_amount_minor = 100

        net_amount_minor = (
            gross_amount_minor
            - fee_amount_minor
        )

        settlement_id = (
            f"SET-{index:03d}"
        )

        bank_reference = (
            f"BANK-REF-{settlement_id}"
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
                "transaction_amount_minor": (
                    gross_amount_minor
                ),
                "settlement_gross_eur_minor": (
                    gross_amount_minor
                ),
                "fee_eur_minor": (
                    fee_amount_minor
                ),
                "settlement_net_eur_minor": (
                    net_amount_minor
                ),
                "psp_fx_rate": (
                    Decimal("1.00000000")
                    if event["currency"]
                    == "EUR"
                    else Decimal(
                        "0.92000000"
                    )
                ),
            }
        )

        settlements.append(
            {
                "settlement_id": (
                    settlement_id
                ),
                "settlement_date": date(
                    2026,
                    1,
                    11,
                ),
                "status": "PAID",
                "currency": "EUR",
                "gross_amount_minor": (
                    gross_amount_minor
                ),
                "fee_amount_minor": (
                    fee_amount_minor
                ),
                "net_payout_minor": (
                    net_amount_minor
                ),
                "bank_reference": (
                    bank_reference
                ),
            }
        )

        statement_transactions.append(
            {
                "bank_transaction_id": (
                    f"BANK-{index:03d}"
                ),
                "payment_reference": (
                    bank_reference
                ),
                "status": "BOOKED",
                "direction": "CREDIT",
                "currency": "EUR",
                "amount_minor": (
                    net_amount_minor
                ),
            }
        )

        event_type = str(
            event["event_type"]
        )

        if event_type == "CAPTURE":
            debit_account = "1200"
            credit_account = "4000"
        else:
            debit_account = "6300"
            credit_account = "1200"

        journal_lines.extend(
            accounting_entry(
                journal_entry_id=(
                    f"JE-{event_id}"
                ),
                source_reference_type=(
                    "FINANCIAL_EVENT"
                ),
                source_reference=event_id,
                debit_account=(
                    debit_account
                ),
                credit_account=(
                    credit_account
                ),
                amount_minor=(
                    gross_amount_minor
                ),
            )
        )

    return {
        "products": products,
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
        "statement_transactions": (
            statement_transactions
        ),
        "journal_lines": (
            journal_lines
        ),
    }