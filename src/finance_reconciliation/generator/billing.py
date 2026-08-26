from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from finance_reconciliation.generator.catalog import ProductDefinition
from finance_reconciliation.generator.config import GeneratorConfig
from finance_reconciliation.generator.ids import IdFactory
from finance_reconciliation.generator.randomness import DeterministicRandom


def utc_datetime(
    value: date,
    *,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime.combine(
        value,
        time(
            hour=hour,
            minute=minute,
            second=second,
            tzinfo=UTC,
        ),
    )


def add_months(value: date, months: int) -> date:
    month_index = (
        value.year * 12
        + value.month
        - 1
        + months
    )

    year = month_index // 12
    month = month_index % 12 + 1

    last_day = calendar.monthrange(
        year,
        month,
    )[1]

    day = min(
        value.day,
        last_day,
    )

    return date(
        year,
        month,
        day,
    )


def add_years(value: date, years: int) -> date:
    year = value.year + years

    last_day = calendar.monthrange(
        year,
        value.month,
    )[1]

    return date(
        year,
        value.month,
        min(value.day, last_day),
    )


def recurring_invoice_dates(
    *,
    started_on: date,
    billing_interval: str,
    window_start: date,
    window_end: date,
    cancelled_on: date | None,
) -> list[date]:
    invoice_dates: list[date] = []

    candidate = started_on

    while candidate < window_start:
        if billing_interval == "MONTH":
            candidate = add_months(candidate, 1)
        elif billing_interval == "YEAR":
            candidate = add_years(candidate, 1)
        else:
            raise ValueError(
                f"Unsupported billing interval: {billing_interval}"
            )

    while candidate <= window_end:
        if (
            cancelled_on is not None
            and candidate > cancelled_on
        ):
            break

        invoice_dates.append(candidate)

        if billing_interval == "MONTH":
            candidate = add_months(candidate, 1)
        else:
            candidate = add_years(candidate, 1)

    return invoice_dates


def calculate_tax_minor(
    subtotal_minor: int,
    tax_rate: float,
) -> int:
    value = (
        Decimal(subtotal_minor)
        * Decimal(str(tax_rate))
    )

    return int(
        value.quantize(
            Decimal(1),
            rounding=ROUND_HALF_UP,
        )
    )


def generate_products(
    *,
    config: GeneratorConfig,
    catalog: list[ProductDefinition],
) -> list[dict[str, Any]]:
    created_on = (
        config.start_date
        - timedelta(days=365)
    )

    timestamp = utc_datetime(created_on)

    return [
        {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "product_family": product.product_family,
            "billing_interval": product.billing_interval,
            "list_price_minor": product.list_price_minor,
            "currency": product.currency,
            "is_active": True,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        for product in catalog
    ]


def generate_subscriptions(
    *,
    config: GeneratorConfig,
    catalog: list[ProductDefinition],
    rng: DeterministicRandom,
    ids: IdFactory,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    volume = config.data["volume"]
    behavior = config.data["behavior"]["subscriptions"]

    product_weights = {
        product.product_id: product.selection_weight
        for product in catalog
    }

    product_by_id = {
        product.product_id: product
        for product in catalog
    }

    status_weights = {
        "CANCELLED": behavior["cancelled_rate"],
        "PAST_DUE": behavior["past_due_rate"],
        "ACTIVE": (
            1
            - behavior["cancelled_rate"]
            - behavior["past_due_rate"]
        ),
    }

    window_length = (
        config.end_date
        - config.start_date
    ).days

    for _ in range(volume["customer_count"]):
        customer_id = ids.next("customer")

        has_subscription = rng.chance(
            volume["active_subscription_rate"]
        )

        if not has_subscription:
            continue

        product_id = rng.weighted_choice(
            product_weights
        )

        product = product_by_id[product_id]

        start_offset = rng.randint(
            -365,
            window_length,
        )

        started_on = (
            config.start_date
            + timedelta(days=start_offset)
        )

        status = rng.weighted_choice(
            status_weights
        )

        cancelled_on: date | None = None

        if status == "CANCELLED":
            cancellation_start = max(
                started_on,
                config.start_date,
            )

            if cancellation_start <= config.end_date:
                cancellation_span = (
                    config.end_date
                    - cancellation_start
                ).days

                cancelled_on = (
                    cancellation_start
                    + timedelta(
                        days=rng.randint(
                            0,
                            cancellation_span,
                        )
                    )
                )
            else:
                cancelled_on = started_on

        started_at = utc_datetime(
            started_on,
            hour=10,
        )

        cancelled_at = (
            utc_datetime(
                cancelled_on,
                hour=12,
            )
            if cancelled_on
            else None
        )

        rows.append(
            {
                "subscription_id": ids.next(
                    "subscription"
                ),
                "customer_id": customer_id,
                "product_id": product.product_id,
                "subscription_status": status,
                "started_at": started_at,
                "cancelled_at": cancelled_at,
                "created_at": started_at,
                "updated_at": (
                    cancelled_at
                    if cancelled_at
                    else started_at
                ),
            }
        )

    return rows


def generate_invoices(
    *,
    config: GeneratorConfig,
    catalog: list[ProductDefinition],
    subscriptions: list[dict[str, Any]],
    ids: IdFactory,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    product_by_id = {
        product.product_id: product
        for product in catalog
    }

    tax_rate = config.data[
        "behavior"
    ]["invoicing"]["tax_rate"]

    for subscription in subscriptions:
        product = product_by_id[
            subscription["product_id"]
        ]

        started_on = (
            subscription["started_at"].date()
        )

        cancelled_at = subscription[
            "cancelled_at"
        ]

        cancelled_on = (
            cancelled_at.date()
            if cancelled_at
            else None
        )

        dates = recurring_invoice_dates(
            started_on=started_on,
            billing_interval=product.billing_interval,
            window_start=config.start_date,
            window_end=config.end_date,
            cancelled_on=cancelled_on,
        )

        for invoice_date in dates:
            subtotal_minor = (
                product.list_price_minor
            )

            tax_minor = calculate_tax_minor(
                subtotal_minor,
                tax_rate,
            )

            total_minor = (
                subtotal_minor
                + tax_minor
            )

            created_at = utc_datetime(
                invoice_date,
                hour=8,
                minute=50,
            )

            rows.append(
                {
                    "invoice_id": ids.next(
                        "invoice"
                    ),
                    "subscription_id": (
                        subscription[
                            "subscription_id"
                        ]
                    ),
                    "customer_id": (
                        subscription["customer_id"]
                    ),
                    "product_id": product.product_id,
                    "invoice_date": invoice_date,
                    "due_date": invoice_date,
                    "currency": product.currency,
                    "subtotal_minor": subtotal_minor,
                    "tax_minor": tax_minor,
                    "total_minor": total_minor,
                    "invoice_status": "OPEN",
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    return rows