from collections import defaultdict

from finance_reconciliation.generator.config import (
    GeneratorConfig,
    load_config,
)
from finance_reconciliation.generator.pipeline import (
    generate_clean_dataset,
)


def test_all_posted_journals_balance() -> None:
    config = load_config()

    data = dict(
        config.data
    )

    data = {
        **config.data,
        "volume": {
            **config.data["volume"],
            "customer_count": 500,
        },
    }

    small_config = GeneratorConfig(
        path=config.path,
        data=data,
    )

    dataset = generate_clean_dataset(
        small_config
    )

    totals = defaultdict(
        lambda: {
            "debit": 0,
            "credit": 0,
        }
    )

    for line in dataset.journal_lines:
        totals[
            line["journal_entry_id"]
        ]["debit"] += (
            line["debit_eur_minor"]
        )

        totals[
            line["journal_entry_id"]
        ]["credit"] += (
            line["credit_eur_minor"]
        )

    assert totals

    for amounts in totals.values():
        assert (
            amounts["debit"]
            ==
            amounts["credit"]
        )