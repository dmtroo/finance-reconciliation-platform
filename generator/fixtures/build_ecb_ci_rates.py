from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

OUTPUT = Path(__file__).with_name("ecb_ci_rates.csv")

START = date(2025, 12, 1)
END = date(2026, 2, 28)

BASE_RATES = {
    "USD": Decimal("0.92500000"),
    "GBP": Decimal("1.18000000"),
    "PLN": Decimal("0.23200000"),
    "SEK": Decimal("0.08900000"),
}

STEP = {
    "USD": Decimal("0.00015000"),
    "GBP": Decimal("0.00012000"),
    "PLN": Decimal("0.00004000"),
    "SEK": Decimal("0.00001500"),
}


def business_dates(start: date, end: date):
    current = start

    while current <= end:
        if current.weekday() < 5:
            yield current

        current += timedelta(days=1)


def main() -> None:
    rows = []

    for index, rate_date in enumerate(
        business_dates(START, END)
    ):
        drift_index = (index % 11) - 5

        for currency, base_rate in BASE_RATES.items():
            rate = (
                base_rate
                + STEP[currency]
                * Decimal(drift_index)
            )

            rows.append(
                {
                    "rate_date": rate_date.isoformat(),
                    "currency": currency,
                    "eur_per_unit": format(
                        rate,
                        ".8f",
                    ),
                }
            )

    with OUTPUT.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=[
                "rate_date",
                "currency",
                "eur_per_unit",
            ],
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Wrote {len(rows)} rows to {OUTPUT}"
    )


if __name__ == "__main__":
    main()