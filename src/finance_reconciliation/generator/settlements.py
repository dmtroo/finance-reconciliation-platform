from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
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


def round_minor(
    value: Decimal,
) -> int:
    return int(
        value.quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


def calculate_psp_fx_rate(
    *,
    reference_rate: Decimal,
    currency: str,
    spread_bps: int,
) -> Decimal:
    if currency == "EUR":
        return Decimal(
            "1.00000000"
        )

    spread = (
        Decimal(spread_bps)
        / Decimal(10000)
    )

    rate = (
        reference_rate
        * (Decimal(1) - spread)
    )

    return rate.quantize(
        Decimal("0.00000001"),
        rounding=ROUND_HALF_UP,
    )


def calculate_capture_fee_minor(
    *,
    gross_eur_minor: int,
    variable_fee_bps: int,
    fixed_fee_eur_minor: int,
) -> int:
    variable = (
        Decimal(abs(gross_eur_minor))
        * Decimal(variable_fee_bps)
        / Decimal(10000)
    )

    return (
        round_minor(variable)
        + fixed_fee_eur_minor
    )


def generate_settlement_sources(
    *,
    config: GeneratorConfig,
    financial_events: list[dict[str, Any]],
    fx: ReferenceFxProvider,
    rng: DeterministicRandom,
    ids: IdFactory,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    settlement_config = config.data[
        "behavior"
    ]["settlements"]

    items_by_eligible_date: dict[
        date,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for event in sorted(
        financial_events,
        key=lambda row: (
            row["event_at"],
            row["financial_event_id"],
        ),
    ):
        currency = event["currency"]

        reference_rate = fx.get_rate(
            currency,
            event["event_at"].date(),
        )

        spread_bps = rng.randint(
            settlement_config[
                "psp_fx_spread_bps_min"
            ],
            settlement_config[
                "psp_fx_spread_bps_max"
            ],
        )

        psp_fx_rate = (
            calculate_psp_fx_rate(
                reference_rate=reference_rate,
                currency=currency,
                spread_bps=spread_bps,
            )
        )

        unsigned_gross_minor = round_minor(
            Decimal(
                event["amount_minor"]
            )
            * psp_fx_rate
        )

        sign = (
            1
            if event["event_type"]
            == "CAPTURE"
            else -1
        )

        gross_eur_minor = (
            sign
            * unsigned_gross_minor
        )

        fee_eur_minor = 0

        if event["event_type"] == "CAPTURE":
            fee_eur_minor = (
                calculate_capture_fee_minor(
                    gross_eur_minor=gross_eur_minor,
                    variable_fee_bps=settlement_config[
                        "variable_fee_bps"
                    ],
                    fixed_fee_eur_minor=settlement_config[
                        "fixed_fee_eur_minor"
                    ],
                )
            )

        net_eur_minor = (
            gross_eur_minor
            - fee_eur_minor
        )

        delay = int(
            rng.weighted_choice(
                settlement_config[
                    "delay_days_weights"
                ]
            )
        )

        eligible_date = (
            event["event_at"].date()
            + timedelta(days=delay)
        )

        items_by_eligible_date[
            eligible_date
        ].append(
            {
                "settlement_item_id": ids.next(
                    "settlement_item"
                ),
                "settlement_id": None,
                "financial_event_id": (
                    event[
                        "financial_event_id"
                    ]
                ),
                "transaction_currency": currency,
                "transaction_amount_minor": (
                    event["amount_minor"]
                ),
                "settlement_gross_eur_minor": (
                    gross_eur_minor
                ),
                "fee_eur_minor": (
                    fee_eur_minor
                ),
                "settlement_net_eur_minor": (
                    net_eur_minor
                ),
                "psp_fx_rate": psp_fx_rate,
            }
        )

    settlements: list[
        dict[str, Any]
    ] = []

    settled_items: list[
        dict[str, Any]
    ] = []

    carry: list[
        dict[str, Any]
    ] = []

    for settlement_date in sorted(
        items_by_eligible_date
    ):
        current_items = (
            carry
            + items_by_eligible_date[
                settlement_date
            ]
        )

        gross = sum(
            item[
                "settlement_gross_eur_minor"
            ]
            for item in current_items
        )

        fee = sum(
            item["fee_eur_minor"]
            for item in current_items
        )

        net = gross - fee

        if net <= 0:
            carry = current_items
            continue

        settlement_id = ids.next(
            "settlement"
        )

        bank_reference = (
            f"PAYOUT-"
            f"{settlement_id.rsplit('-', 1)[-1]}"
        )

        for item in current_items:
            item["settlement_id"] = (
                settlement_id
            )

            settled_items.append(
                item
            )

        settlements.append(
            {
                "settlement_id": (
                    settlement_id
                ),
                "settlement_date": (
                    settlement_date
                ),
                "settlement_currency": (
                    "EUR"
                ),
                "gross_amount_minor": (
                    gross
                ),
                "fee_amount_minor": (
                    fee
                ),
                "net_payout_minor": (
                    net
                ),
                "status": "PAID",
                "bank_reference": (
                    bank_reference
                ),
                "created_at": (
                    event_timestamp(
                        settlement_date
                    )
                ),
            }
        )

        carry = []

    if carry:
        oldest_event_count = len(
            carry
        )

        raise ValueError(
            "Clean generator ended with "
            f"{oldest_event_count} negative-net "
            "settlement items that could not be "
            "absorbed by a later positive payout"
        )

    return settlements, settled_items


def event_timestamp(
    value: date,
):
    from finance_reconciliation.generator.billing import (
        utc_datetime,
    )

    return utc_datetime(
        value,
        hour=16,
    )