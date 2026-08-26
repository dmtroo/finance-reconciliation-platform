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
    ] = 250

    return GeneratorConfig(
        path=base.path,
        data=data,
    )


def test_clean_generation_is_deterministic() -> None:
    config = small_config()

    first = generate_clean_dataset(
        config
    )

    second = generate_clean_dataset(
        config
    )

    assert first == second


def test_clean_invoices_balance() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    for invoice in dataset.invoices:
        assert (
            invoice["total_minor"]
            ==
            invoice["subtotal_minor"]
            + invoice["tax_minor"]
        )


def test_clean_paid_invoice_has_one_successful_attempt() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    attempts_by_invoice = {}

    for attempt in dataset.payment_attempts:
        attempts_by_invoice.setdefault(
            attempt["invoice_id"],
            [],
        ).append(attempt)

    for invoice in dataset.invoices:
        successful = [
            attempt
            for attempt in attempts_by_invoice[
                invoice["invoice_id"]
            ]
            if attempt["status"]
            == "SUCCEEDED"
        ]

        if invoice["invoice_status"] == "PAID":
            assert len(successful) == 1

        if (
            invoice["invoice_status"]
            == "UNCOLLECTIBLE"
        ):
            assert len(successful) == 0


def test_every_capture_matches_successful_attempt() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    successful_attempts = {
        attempt["payment_attempt_id"]: attempt
        for attempt in dataset.payment_attempts
        if attempt["status"] == "SUCCEEDED"
    }

    captures = [
        event
        for event in dataset.financial_events
        if event["event_type"]
        == "CAPTURE"
    ]

    assert len(captures) == len(
        successful_attempts
    )

    for capture in captures:
        attempt = successful_attempts[
            capture["payment_attempt_id"]
        ]

        assert (
            capture["amount_minor"]
            ==
            attempt["amount_minor"]
        )

        assert (
            capture["currency"]
            ==
            attempt["currency"]
        )


def test_refunds_and_chargebacks_reference_capture() -> None:
    dataset = generate_clean_dataset(
        small_config()
    )

    capture_by_id = {
        event["financial_event_id"]: event
        for event in dataset.financial_events
        if event["event_type"]
        == "CAPTURE"
    }

    for event in dataset.financial_events:
        if event["event_type"] not in {
            "REFUND",
            "CHARGEBACK",
        }:
            continue

        capture = capture_by_id[
            event["original_capture_id"]
        ]

        assert (
            event["invoice_id"]
            ==
            capture["invoice_id"]
        )

        assert (
            event["currency"]
            ==
            capture["currency"]
        )

        assert event["amount_minor"] > 0