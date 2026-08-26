from copy import deepcopy

from finance_reconciliation.generator.config import (
    GeneratorConfig,
    load_config,
)
from finance_reconciliation.generator.pipeline import (
    generate_clean_dataset,
)


def small_config() -> GeneratorConfig:
    base = load_config()

    data = deepcopy(
        base.data
    )

    data["volume"][
        "customer_count"
    ] = 1000

    return GeneratorConfig(
        path=base.path,
        data=data,
    )


def test_settlement_header_equals_items() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    items_by_settlement = {}

    for item in dataset.settlement_items:
        items_by_settlement.setdefault(
            item["settlement_id"],
            [],
        ).append(item)

    for settlement in dataset.settlements:
        items = items_by_settlement[
            settlement["settlement_id"]
        ]

        gross = sum(
            item[
                "settlement_gross_eur_minor"
            ]
            for item in items
        )

        fees = sum(
            item["fee_eur_minor"]
            for item in items
        )

        net = sum(
            item[
                "settlement_net_eur_minor"
            ]
            for item in items
        )

        assert (
            settlement[
                "gross_amount_minor"
            ]
            == gross
        )

        assert (
            settlement[
                "fee_amount_minor"
            ]
            == fees
        )

        assert (
            settlement[
                "net_payout_minor"
            ]
            == net
        )

        assert (
            settlement[
                "net_payout_minor"
            ]
            > 0
        )


def test_financial_event_is_settled_at_most_once() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    event_ids = [
        item[
            "financial_event_id"
        ]
        for item
        in dataset.settlement_items
    ]

    assert len(event_ids) == len(
        set(event_ids)
    )


def test_paid_settlement_has_one_bank_receipt() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    bank_by_reference = {}

    for row in dataset.bank_transactions:
        bank_by_reference.setdefault(
            row["payment_reference"],
            [],
        ).append(row)

    for settlement in dataset.settlements:
        matching = bank_by_reference[
            settlement["bank_reference"]
        ]

        assert len(matching) == 1

        bank = matching[0]

        assert (
            bank["amount_minor"]
            ==
            settlement[
                "net_payout_minor"
            ]
        )

        assert bank["currency"] == "EUR"
        assert bank["direction"] == "CREDIT"
        assert bank["status"] == "BOOKED"

def test_non_eur_psp_fx_is_not_reference_fx() -> None:
    from finance_reconciliation.generator.fx import (
        ReferenceFxProvider,
    )

    config = small_config()

    dataset = generate_clean_dataset(
        config
    )

    fx = ReferenceFxProvider.from_csv(
        config.fx_reference_path
    )

    event_by_id = {
        event["financial_event_id"]: event
        for event
        in dataset.financial_events
    }

    checked = 0

    for item in dataset.settlement_items:
        if (
            item[
                "transaction_currency"
            ]
            == "EUR"
        ):
            continue

        event = event_by_id[
            item["financial_event_id"]
        ]

        reference = fx.get_rate(
            event["currency"],
            event["event_at"].date(),
        )

        assert (
            item["psp_fx_rate"]
            != reference
        )

        checked += 1

    assert checked > 0