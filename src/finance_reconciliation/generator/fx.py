from __future__ import annotations

import csv
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class FxRate:
    rate_date: date
    currency: str
    eur_per_unit: Decimal


class ReferenceFxProvider:
    """Normalized EUR-per-unit FX reference for generator logic."""

    def __init__(
        self,
        rates: dict[str, list[FxRate]],
    ) -> None:
        self._rates = rates

    @classmethod
    def from_csv(
        cls,
        path: Path,
    ) -> ReferenceFxProvider:
        rates: dict[str, list[FxRate]] = {}

        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as file_handle:
            reader = csv.DictReader(
                file_handle
            )

            for row in reader:
                currency = row[
                    "currency"
                ]

                rates.setdefault(
                    currency,
                    [],
                ).append(
                    FxRate(
                        rate_date=date.fromisoformat(
                            row["rate_date"]
                        ),
                        currency=currency,
                        eur_per_unit=Decimal(
                            row["eur_per_unit"]
                        ),
                    )
                )

        for currency, currency_rates in rates.items():
            currency_rates.sort(
                key=lambda item: item.rate_date
            )

        return cls(rates)

    def get_rate(
        self,
        currency: str,
        event_date: date,
    ) -> Decimal:
        if currency == "EUR":
            return Decimal(
                "1.00000000"
            )

        if currency not in self._rates:
            raise LookupError(
                f"No FX series for {currency}"
            )

        series = self._rates[
            currency
        ]

        dates = [
            item.rate_date
            for item in series
        ]

        index = bisect_right(
            dates,
            event_date,
        ) - 1

        if index < 0:
            raise LookupError(
                f"No {currency} FX rate on or before {event_date}"
            )

        return series[
            index
        ].eur_per_unit