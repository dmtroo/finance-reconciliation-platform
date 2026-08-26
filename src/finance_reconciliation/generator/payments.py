from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from finance_reconciliation.generator.billing import utc_datetime
from finance_reconciliation.generator.config import GeneratorConfig
from finance_reconciliation.generator.ids import IdFactory
from finance_reconciliation.generator.randomness import DeterministicRandom


def _id_suffix(value: str) -> str:
    return value.rsplit("-", 1)[-1]


def generate_payment_sources(
    *,
    config: GeneratorConfig,
    invoices: list[dict[str, Any]],
    rng: DeterministicRandom,
    ids: IdFactory,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    attempts: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    payment_config = config.data[
        "behavior"
    ]["payments"]

    captures: list[dict[str, Any]] = []

    for invoice in sorted(
        invoices,
        key=lambda row: row["invoice_id"],
    ):
        method = rng.weighted_choice(
            payment_config[
                "payment_method_weights"
            ]
        )

        first_attempt_at = (
            invoice["created_at"]
            + timedelta(minutes=10)
        )

        first_declines = rng.chance(
            payment_config[
                "first_attempt_decline_rate"
            ]
        )

        if not first_declines:
            attempt = _successful_attempt(
                invoice=invoice,
                method=method,
                attempted_at=first_attempt_at,
                ids=ids,
            )

            attempts.append(attempt)

            capture = _capture_event(
                invoice=invoice,
                attempt=attempt,
                ids=ids,
            )

            events.append(capture)
            captures.append(capture)

            _mark_paid(
                invoice,
                attempt,
            )

            continue

        attempts.append(
            _declined_attempt(
                invoice=invoice,
                method=method,
                attempted_at=first_attempt_at,
                ids=ids,
            )
        )

        should_retry = (
            payment_config["max_attempts"] >= 2
            and rng.chance(
                payment_config[
                    "retry_after_decline_rate"
                ]
            )
        )

        if not should_retry:
            invoice[
                "invoice_status"
            ] = "UNCOLLECTIBLE"

            invoice["updated_at"] = (
                first_attempt_at
                + timedelta(minutes=1)
            )

            continue

        retry_at = (
            first_attempt_at
            + timedelta(minutes=5)
        )

        attempt = _successful_attempt(
            invoice=invoice,
            method=method,
            attempted_at=retry_at,
            ids=ids,
        )

        attempts.append(attempt)

        capture = _capture_event(
            invoice=invoice,
            attempt=attempt,
            ids=ids,
        )

        events.append(capture)
        captures.append(capture)

        _mark_paid(
            invoice,
            attempt,
        )

    _generate_post_capture_events(
        config=config,
        captures=captures,
        events=events,
        rng=rng,
        ids=ids,
    )

    return attempts, events


def _declined_attempt(
    *,
    invoice: dict[str, Any],
    method: str,
    attempted_at,
    ids: IdFactory,
) -> dict[str, Any]:
    attempt_id = ids.next(
        "payment_attempt"
    )

    return {
        "payment_attempt_id": attempt_id,
        "invoice_id": invoice["invoice_id"],
        "provider_customer_id": (
            f"PSP-{invoice['customer_id']}"
        ),
        "attempted_at": attempted_at,
        "currency": invoice["currency"],
        "amount_minor": invoice["total_minor"],
        "payment_method_type": method,
        "status": "DECLINED",
        "failure_code": "INSUFFICIENT_FUNDS",
        "provider_transaction_id": None,
    }


def _successful_attempt(
    *,
    invoice: dict[str, Any],
    method: str,
    attempted_at,
    ids: IdFactory,
) -> dict[str, Any]:
    attempt_id = ids.next(
        "payment_attempt"
    )

    suffix = _id_suffix(
        attempt_id
    )

    return {
        "payment_attempt_id": attempt_id,
        "invoice_id": invoice["invoice_id"],
        "provider_customer_id": (
            f"PSP-{invoice['customer_id']}"
        ),
        "attempted_at": attempted_at,
        "currency": invoice["currency"],
        "amount_minor": invoice["total_minor"],
        "payment_method_type": method,
        "status": "SUCCEEDED",
        "failure_code": None,
        "provider_transaction_id": (
            f"PSP-TXN-{suffix}"
        ),
    }


def _capture_event(
    *,
    invoice: dict[str, Any],
    attempt: dict[str, Any],
    ids: IdFactory,
) -> dict[str, Any]:
    event_id = ids.next(
        "financial_event"
    )

    suffix = _id_suffix(
        event_id
    )

    return {
        "financial_event_id": event_id,
        "event_type": "CAPTURE",
        "payment_attempt_id": (
            attempt["payment_attempt_id"]
        ),
        "invoice_id": invoice["invoice_id"],
        "original_capture_id": None,
        "event_at": (
            attempt["attempted_at"]
            + timedelta(seconds=2)
        ),
        "currency": invoice["currency"],
        "amount_minor": invoice["total_minor"],
        "provider_transaction_id": (
            f"PSP-EVT-{suffix}"
        ),
    }


def _mark_paid(
    invoice: dict[str, Any],
    attempt: dict[str, Any],
) -> None:
    invoice["invoice_status"] = "PAID"

    invoice["updated_at"] = (
        attempt["attempted_at"]
        + timedelta(minutes=1)
    )


def _generate_post_capture_events(
    *,
    config: GeneratorConfig,
    captures: list[dict[str, Any]],
    events: list[dict[str, Any]],
    rng: DeterministicRandom,
    ids: IdFactory,
) -> None:
    refund_config = config.data[
        "behavior"
    ]["refunds"]

    chargeback_config = config.data[
        "behavior"
    ]["chargebacks"]

    for capture in captures:
        generated_refund = False

        if rng.chance(
            refund_config[
                "capture_refund_rate"
            ]
        ):
            delay = rng.randint(
                refund_config["min_delay_days"],
                refund_config["max_delay_days"],
            )

            refund_date = (
                capture["event_at"].date()
                + timedelta(days=delay)
            )

            if refund_date <= config.end_date:
                fraction = Decimal(
                    rng.weighted_choice(
                        refund_config[
                            "amount_fraction_weights"
                        ]
                    )
                )

                amount_minor = int(
                    (
                        Decimal(
                            capture["amount_minor"]
                        )
                        * fraction
                    ).quantize(
                        Decimal(1),
                        rounding=ROUND_HALF_UP,
                    )
                )

                event_id = ids.next(
                    "financial_event"
                )

                events.append(
                    {
                        "financial_event_id": event_id,
                        "event_type": "REFUND",
                        "payment_attempt_id": None,
                        "invoice_id": (
                            capture["invoice_id"]
                        ),
                        "original_capture_id": (
                            capture[
                                "financial_event_id"
                            ]
                        ),
                        "event_at": utc_datetime(
                            refund_date,
                            hour=12,
                        ),
                        "currency": capture["currency"],
                        "amount_minor": amount_minor,
                        "provider_transaction_id": (
                            f"PSP-EVT-"
                            f"{_id_suffix(event_id)}"
                        ),
                    }
                )

                generated_refund = True

        # v1 deliberately avoids combining natural refunds
        # and chargebacks on the same capture.
        if generated_refund:
            continue

        if not rng.chance(
            chargeback_config[
                "capture_chargeback_rate"
            ]
        ):
            continue

        delay = rng.randint(
            chargeback_config[
                "min_delay_days"
            ],
            chargeback_config[
                "max_delay_days"
            ],
        )

        chargeback_date = (
            capture["event_at"].date()
            + timedelta(days=delay)
        )

        if chargeback_date > config.end_date:
            continue

        event_id = ids.next(
            "financial_event"
        )

        events.append(
            {
                "financial_event_id": event_id,
                "event_type": "CHARGEBACK",
                "payment_attempt_id": None,
                "invoice_id": capture["invoice_id"],
                "original_capture_id": (
                    capture[
                        "financial_event_id"
                    ]
                ),
                "event_at": utc_datetime(
                    chargeback_date,
                    hour=13,
                ),
                "currency": capture["currency"],
                "amount_minor": (
                    capture["amount_minor"]
                ),
                "provider_transaction_id": (
                    f"PSP-EVT-"
                    f"{_id_suffix(event_id)}"
                ),
            }
        )