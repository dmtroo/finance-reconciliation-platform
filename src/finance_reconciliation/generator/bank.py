from __future__ import annotations

from datetime import timedelta
from typing import Any

from finance_reconciliation.generator.config import (
    GeneratorConfig,
)
from finance_reconciliation.generator.ids import (
    IdFactory,
)
from finance_reconciliation.generator.randomness import (
    DeterministicRandom,
)


def generate_bank_transactions(
    *,
    config: GeneratorConfig,
    settlements: list[dict[str, Any]],
    rng: DeterministicRandom,
    ids: IdFactory,
) -> list[dict[str, Any]]:
    weights = config.data[
        "behavior"
    ]["bank"][
        "posting_delay_days_weights"
    ]

    rows: list[
        dict[str, Any]
    ] = []

    for settlement in sorted(
        settlements,
        key=lambda row: (
            row["settlement_date"],
            row["settlement_id"],
        ),
    ):
        if settlement["status"] != "PAID":
            continue

        delay = int(
            rng.weighted_choice(
                weights
            )
        )

        booking_date = (
            settlement[
                "settlement_date"
            ]
            + timedelta(days=delay)
        )

        rows.append(
            {
                "bank_transaction_id": (
                    ids.next(
                        "bank_transaction"
                    )
                ),
                "booking_date": (
                    booking_date
                ),
                "value_date": booking_date,
                "direction": "CREDIT",
                "currency": "EUR",
                "amount_minor": (
                    settlement[
                        "net_payout_minor"
                    ]
                ),
                "counterparty": (
                    "PSP EUROPE"
                ),
                "payment_reference": (
                    settlement[
                        "bank_reference"
                    ]
                ),
                "status": "BOOKED",
            }
        )

    return rows