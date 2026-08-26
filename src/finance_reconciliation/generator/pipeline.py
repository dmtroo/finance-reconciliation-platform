from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finance_reconciliation.generator.accounting import (
    generate_accounting_journals,
)
from finance_reconciliation.generator.bank import (
    generate_bank_transactions,
)
from finance_reconciliation.generator.billing import (
    generate_invoices,
    generate_products,
    generate_subscriptions,
)
from finance_reconciliation.generator.catalog import load_catalog
from finance_reconciliation.generator.columns import CSV_FIELDS
from finance_reconciliation.generator.config import GeneratorConfig
from finance_reconciliation.generator.fx import (
    ReferenceFxProvider,
)
from finance_reconciliation.generator.ids import IdFactory
from finance_reconciliation.generator.io import write_csv
from finance_reconciliation.generator.payments import generate_payment_sources
from finance_reconciliation.generator.randomness import DeterministicRandom
from finance_reconciliation.generator.settlements import (
    generate_settlement_sources,
)


@dataclass
class CleanDataset:
    products: list[dict[str, Any]]
    subscriptions: list[dict[str, Any]]
    invoices: list[dict[str, Any]]

    payment_attempts: list[dict[str, Any]]
    financial_events: list[dict[str, Any]]

    settlements: list[dict[str, Any]]
    settlement_items: list[dict[str, Any]]

    bank_transactions: list[dict[str, Any]]

    journal_lines: list[dict[str, Any]]

def generate_clean_dataset(
    config: GeneratorConfig,
) -> CleanDataset:
    if config.scenario != "clean":
        raise ValueError(
            "Commit 7 generator supports only scenario=clean"
        )

    if config.data["anomalies"]["enabled"]:
        raise ValueError(
            "Anomaly generation is not implemented in the clean pipeline"
        )

    rng = DeterministicRandom(
        config.seed
    )

    ids = IdFactory()

    catalog = load_catalog(
        config.catalog_path
    )

    products = generate_products(
        config=config,
        catalog=catalog,
    )

    subscriptions = generate_subscriptions(
        config=config,
        catalog=catalog,
        rng=rng,
        ids=ids,
    )

    invoices = generate_invoices(
        config=config,
        catalog=catalog,
        subscriptions=subscriptions,
        ids=ids,
    )

    payment_attempts, financial_events = (
        generate_payment_sources(
            config=config,
            invoices=invoices,
            rng=rng,
            ids=ids,
        )
    )

    fx = ReferenceFxProvider.from_csv(
        config.fx_reference_path
    )

    settlements, settlement_items = (
        generate_settlement_sources(
            config=config,
            financial_events=financial_events,
            fx=fx,
            rng=rng,
            ids=ids,
        )
    )

    bank_transactions = (
        generate_bank_transactions(
            config=config,
            settlements=settlements,
            rng=rng,
            ids=ids,
        )
    )

    journal_lines = (
        generate_accounting_journals(
            config=config,
            financial_events=financial_events,
            settlements=settlements,
            fx=fx,
            rng=rng,
            ids=ids,
        )
    )

    return CleanDataset(
        products=products,
        subscriptions=subscriptions,
        invoices=invoices,
        payment_attempts=payment_attempts,
        financial_events=financial_events,
        settlements=settlements,
        settlement_items=settlement_items,
        bank_transactions=bank_transactions,
        journal_lines=journal_lines,
    )

def write_clean_dataset(
    *,
    config: GeneratorConfig,
    dataset: CleanDataset,
) -> dict[str, int]:
    output_dir = config.output_dir

    counts = {
        "billing/products": write_csv(
            output_dir
            / "billing"
            / "products.csv",
            rows=dataset.products,
            fieldnames=CSV_FIELDS[
                "billing/products"
            ],
        ),
        "billing/subscriptions": write_csv(
            output_dir
            / "billing"
            / "subscriptions.csv",
            rows=dataset.subscriptions,
            fieldnames=CSV_FIELDS[
                "billing/subscriptions"
            ],
        ),
        "billing/invoices": write_csv(
            output_dir
            / "billing"
            / "invoices.csv",
            rows=dataset.invoices,
            fieldnames=CSV_FIELDS[
                "billing/invoices"
            ],
        ),
        "psp/payment_attempts": write_csv(
            output_dir
            / "psp"
            / "payment_attempts.csv",
            rows=dataset.payment_attempts,
            fieldnames=CSV_FIELDS[
                "psp/payment_attempts"
            ],
        ),
        "psp/financial_events": write_csv(
            output_dir
            / "psp"
            / "financial_events.csv",
            rows=dataset.financial_events,
            fieldnames=CSV_FIELDS[
                "psp/financial_events"
            ],
        ),
                "psp/settlements": write_csv(
            output_dir
            / "psp"
            / "settlements.csv",
            rows=dataset.settlements,
            fieldnames=CSV_FIELDS[
                "psp/settlements"
            ],
        ),
        "psp/settlement_items": write_csv(
            output_dir
            / "psp"
            / "settlement_items.csv",
            rows=dataset.settlement_items,
            fieldnames=CSV_FIELDS[
                "psp/settlement_items"
            ],
        ),
        "bank/statement_transactions": write_csv(
            output_dir
            / "bank"
            / "statement_transactions.csv",
            rows=dataset.bank_transactions,
            fieldnames=CSV_FIELDS[
                "bank/statement_transactions"
            ],
        ),
        "accounting/journal_lines": write_csv(
            output_dir
            / "accounting"
            / "journal_lines.csv",
            rows=dataset.journal_lines,
            fieldnames=CSV_FIELDS[
                "accounting/journal_lines"
            ],
        ),
    }

    return counts