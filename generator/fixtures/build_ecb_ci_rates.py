from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


NORMALIZED_OUTPUT = Path(__file__).with_name(
    "ecb_ci_rates.csv"
)

RAW_OUTPUT = Path(__file__).with_name(
    "ecb_raw_ci_rates.csv"
)

START = date(2025, 12, 1)
END = date(2026, 2, 28)

# Relevant ECB/TARGET publication gaps for the fixed CI window.
CLOSED_DATES = {
    date(2025, 12, 25),
    date(2025, 12, 26),
    date(2026, 1, 1),
}

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


def available_dates(
    start: date,
    end: date,
):
    current = start

    while current <= end:
        if (
            current.weekday() < 5
            and current not in CLOSED_DATES
        ):
            yield current

        current += timedelta(days=1)


def write_csv(
    path: Path,
    *,
    rows: list[dict[str, str]],
    fieldnames: list[str],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    normalized_rows = []
    raw_rows = []

    for index, rate_date in enumerate(
        available_dates(
            START,
            END,
        )
    ):
        drift_index = (
            index % 11
        ) - 5

        for currency, base_rate in BASE_RATES.items():
            eur_per_unit = (
                base_rate
                + STEP[currency]
                * Decimal(drift_index)
            ).quantize(
                Decimal("0.00000001"),
                rounding=ROUND_HALF_UP,
            )

            units_per_eur = (
                Decimal("1")
                / eur_per_unit
            ).quantize(
                Decimal("0.00000001"),
                rounding=ROUND_HALF_UP,
            )

            normalized_rows.append(
                {
                    "rate_date": (
                        rate_date.isoformat()
                    ),
                    "currency": currency,
                    "eur_per_unit": format(
                        eur_per_unit,
                        ".8f",
                    ),
                }
            )

            raw_rows.append(
                {
                    "rate_date": (
                        rate_date.isoformat()
                    ),
                    "currency": currency,
                    "units_per_eur": format(
                        units_per_eur,
                        ".8f",
                    ),
                }
            )

    write_csv(
        NORMALIZED_OUTPUT,
        rows=normalized_rows,
        fieldnames=[
            "rate_date",
            "currency",
            "eur_per_unit",
        ],
    )

    write_csv(
        RAW_OUTPUT,
        rows=raw_rows,
        fieldnames=[
            "rate_date",
            "currency",
            "units_per_eur",
        ],
    )

    print(
        f"Wrote {len(normalized_rows)} normalized rows "
        f"to {NORMALIZED_OUTPUT}"
    )

    print(
        f"Wrote {len(raw_rows)} source-oriented rows "
        f"to {RAW_OUTPUT}"
    )


if __name__ == "__main__":
    main()