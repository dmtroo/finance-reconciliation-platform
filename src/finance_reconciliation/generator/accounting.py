from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from finance_reconciliation.generator.config import (
    GeneratorConfig,
)
from finance_reconciliation.generator.fx import (
    ReferenceFxProvider,
)
from finance_reconciliation.generator.ids import (
    IdFactory,
)
from finance_reconciliation.generator.randomness import (
    DeterministicRandom,
)

ACCOUNTS = {
    "1100": "BANK",
    "1200": "PSP_CLEARING",
    "4000": "SALES_CLEARING",
    "6100": "PAYMENT_PROCESSING_FEES",
    "6200": "CHARGEBACK_LOSS",
    "6300": "CUSTOMER_REFUNDS",
}


def eur_minor(
    *,
    amount_minor: int,
    eur_per_unit: Decimal,
) -> int:
    return int(
        (
            Decimal(amount_minor)
            * eur_per_unit
        ).quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


def _posting_delay(
    *,
    config: GeneratorConfig,
    rng: DeterministicRandom,
) -> int:
    return int(
        rng.weighted_choice(
            config.data[
                "behavior"
            ]["accounting"][
                "posting_delay_days_weights"
            ]
        )
    )


def _line(
    *,
    ids: IdFactory,
    journal_entry_id: str,
    posting_date,
    account_code: str,
    debit_minor: int,
    credit_minor: int,
    source_reference_type: str,
    source_reference: str,
    created_at,
) -> dict[str, Any]:
    return {
        "journal_line_id": ids.next(
            "journal_line"
        ),
        "journal_entry_id": (
            journal_entry_id
        ),
        "posting_date": posting_date,
        "account_code": account_code,
        "account_name": (
            ACCOUNTS[account_code]
        ),
        "debit_eur_minor": (
            debit_minor
        ),
        "credit_eur_minor": (
            credit_minor
        ),
        "source_system": "PSP",
        "source_reference_type": (
            source_reference_type
        ),
        "source_reference": (
            source_reference
        ),
        "journal_status": "POSTED",
        "created_at": created_at,
    }


def generate_accounting_journals(
    *,
    config: GeneratorConfig,
    financial_events: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
    fx: ReferenceFxProvider,
    rng: DeterministicRandom,
    ids: IdFactory,
) -> list[dict[str, Any]]:
    from finance_reconciliation.generator.billing import (
        utc_datetime,
    )

    rows: list[
        dict[str, Any]
    ] = []

    for event in sorted(
        financial_events,
        key=lambda row: (
            row["event_at"],
            row["financial_event_id"],
        ),
    ):
        rate = fx.get_rate(
            event["currency"],
            event["event_at"].date(),
        )

        amount_eur_minor = eur_minor(
            amount_minor=event[
                "amount_minor"
            ],
            eur_per_unit=rate,
        )

        posting_date = (
            event["event_at"].date()
            + timedelta(
                days=_posting_delay(
                    config=config,
                    rng=rng,
                )
            )
        )

        journal_entry_id = ids.next(
            "journal_entry"
        )

        created_at = utc_datetime(
            posting_date,
            hour=7,
            minute=30,
        )

        event_type = event[
            "event_type"
        ]

        if event_type == "CAPTURE":
            debit_account = "1200"
            credit_account = "4000"

        elif event_type == "REFUND":
            debit_account = "6300"
            credit_account = "1200"

        elif event_type == "CHARGEBACK":
            debit_account = "6200"
            credit_account = "1200"

        else:
            raise ValueError(
                f"Unsupported event type: {event_type}"
            )

        rows.append(
            _line(
                ids=ids,
                journal_entry_id=journal_entry_id,
                posting_date=posting_date,
                account_code=debit_account,
                debit_minor=amount_eur_minor,
                credit_minor=0,
                source_reference_type=(
                    "FINANCIAL_EVENT"
                ),
                source_reference=event[
                    "financial_event_id"
                ],
                created_at=created_at,
            )
        )

        rows.append(
            _line(
                ids=ids,
                journal_entry_id=journal_entry_id,
                posting_date=posting_date,
                account_code=credit_account,
                debit_minor=0,
                credit_minor=amount_eur_minor,
                source_reference_type=(
                    "FINANCIAL_EVENT"
                ),
                source_reference=event[
                    "financial_event_id"
                ],
                created_at=created_at,
            )
        )

    for settlement in sorted(
        settlements,
        key=lambda row: (
            row["settlement_date"],
            row["settlement_id"],
        ),
    ):
        posting_date = (
            settlement[
                "settlement_date"
            ]
            + timedelta(
                days=_posting_delay(
                    config=config,
                    rng=rng,
                )
            )
        )

        journal_entry_id = ids.next(
            "journal_entry"
        )

        created_at = utc_datetime(
            posting_date,
            hour=7,
            minute=30,
        )

        source_reference = settlement[
            "settlement_id"
        ]

        rows.append(
            _line(
                ids=ids,
                journal_entry_id=journal_entry_id,
                posting_date=posting_date,
                account_code="1100",
                debit_minor=settlement[
                    "net_payout_minor"
                ],
                credit_minor=0,
                source_reference_type=(
                    "SETTLEMENT"
                ),
                source_reference=source_reference,
                created_at=created_at,
            )
        )

        if (
            settlement[
                "fee_amount_minor"
            ]
            > 0
        ):
            rows.append(
                _line(
                    ids=ids,
                    journal_entry_id=journal_entry_id,
                    posting_date=posting_date,
                    account_code="6100",
                    debit_minor=settlement[
                        "fee_amount_minor"
                    ],
                    credit_minor=0,
                    source_reference_type=(
                        "SETTLEMENT"
                    ),
                    source_reference=source_reference,
                    created_at=created_at,
                )
            )

        rows.append(
            _line(
                ids=ids,
                journal_entry_id=journal_entry_id,
                posting_date=posting_date,
                account_code="1200",
                debit_minor=0,
                credit_minor=settlement[
                    "gross_amount_minor"
                ],
                source_reference_type=(
                    "SETTLEMENT"
                ),
                source_reference=source_reference,
                created_at=created_at,
            )
        )

    return rows