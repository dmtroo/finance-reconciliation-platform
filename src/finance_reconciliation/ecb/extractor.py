from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from pathlib import Path

import requests

from finance_reconciliation.paths import (
    PROJECT_ROOT,
    resolve_project_path,
)

ECB_API_URL = (
    "https://data-api.ecb.europa.eu/"
    "service/data/EXR/"
    "D.USD+GBP+PLN+SEK.EUR.SP00.A"
)

ECB_CURRENCIES = (
    "USD",
    "GBP",
    "PLN",
    "SEK",
)

RAW_FIXTURE = (
    PROJECT_ROOT
    / "generator"
    / "fixtures"
    / "ecb_raw_ci_rates.csv"
)


class EcbMode(str, Enum):
    API = "api"
    FIXTURE = "fixture"


@dataclass(frozen=True)
class EcbObservation:
    rate_date: date
    currency: str
    units_per_eur: Decimal


@dataclass(frozen=True)
class EcbExtractionResult:
    raw_path: Path
    reference_path: Path
    row_count: int
    effective_start_date: date
    end_date: date


def _validate_observations(
    observations: list[EcbObservation],
) -> list[EcbObservation]:
    if not observations:
        raise ValueError(
            "ECB extraction produced zero observations"
        )

    seen: set[
        tuple[date, str]
    ] = set()

    for observation in observations:
        key = (
            observation.rate_date,
            observation.currency,
        )

        if key in seen:
            raise ValueError(
                f"Duplicate ECB observation: {key}"
            )

        seen.add(key)

        if (
            observation.currency
            not in ECB_CURRENCIES
        ):
            raise ValueError(
                "Unexpected ECB currency: "
                f"{observation.currency}"
            )

        if observation.units_per_eur <= 0:
            raise ValueError(
                "ECB rate must be positive: "
                f"{observation}"
            )

    return sorted(
        observations,
        key=lambda item: (
            item.rate_date,
            item.currency,
        ),
    )


def parse_api_csv(
    text: str,
) -> list[EcbObservation]:
    reader = csv.DictReader(
        io.StringIO(
            text.lstrip("\ufeff")
        )
    )

    required = {
        "FREQ",
        "CURRENCY",
        "CURRENCY_DENOM",
        "EXR_TYPE",
        "EXR_SUFFIX",
        "TIME_PERIOD",
        "OBS_VALUE",
    }

    actual = set(
        reader.fieldnames
        or []
    )

    missing = required - actual

    if missing:
        raise ValueError(
            "ECB API response is missing columns: "
            f"{sorted(missing)}"
        )

    observations = []

    for row in reader:
        if row["FREQ"] != "D":
            raise ValueError(
                "Expected daily ECB observations"
            )

        if row[
            "CURRENCY_DENOM"
        ] != "EUR":
            raise ValueError(
                "Expected EUR denominator"
            )

        if row["EXR_TYPE"] != "SP00":
            raise ValueError(
                "Expected ECB spot reference rate"
            )

        if row["EXR_SUFFIX"] != "A":
            raise ValueError(
                "Expected EXR average series"
            )

        observations.append(
            EcbObservation(
                rate_date=date.fromisoformat(
                    row["TIME_PERIOD"]
                ),
                currency=row["CURRENCY"],
                units_per_eur=Decimal(
                    row["OBS_VALUE"]
                ),
            )
        )

    return _validate_observations(
        observations
    )


def read_raw_csv(
    path: str | Path,
) -> list[EcbObservation]:
    resolved = resolve_project_path(
        path
    )

    with resolved.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        reader = csv.DictReader(
            file_handle
        )

        expected = [
            "rate_date",
            "currency",
            "units_per_eur",
        ]

        if reader.fieldnames != expected:
            raise ValueError(
                f"Unexpected ECB extract header in {resolved}. "
                f"Expected {expected}; "
                f"got {reader.fieldnames}"
            )

        observations = [
            EcbObservation(
                rate_date=date.fromisoformat(
                    row["rate_date"]
                ),
                currency=row["currency"],
                units_per_eur=Decimal(
                    row["units_per_eur"]
                ),
            )
            for row in reader
        ]

    return _validate_observations(
        observations
    )


def fetch_api_observations(
    *,
    start_date: date,
    end_date: date,
) -> list[EcbObservation]:
    response = requests.get(
        ECB_API_URL,
        params={
            "startPeriod": (
                start_date.isoformat()
            ),
            "endPeriod": (
                end_date.isoformat()
            ),
            "detail": "dataonly",
            "format": "csvdata",
        },
        headers={
            "User-Agent": (
                "finance-reconciliation-platform/0.1"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    return parse_api_csv(
        response.text
    )


def _write_raw_csv(
    *,
    path: Path,
    observations: list[EcbObservation],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle,
            fieldnames=[
                "rate_date",
                "currency",
                "units_per_eur",
            ],
            lineterminator="\n",
        )

        writer.writeheader()

        for observation in observations:
            writer.writerow(
                {
                    "rate_date": (
                        observation
                        .rate_date
                        .isoformat()
                    ),
                    "currency": (
                        observation.currency
                    ),
                    "units_per_eur": format(
                        observation.units_per_eur,
                        "f",
                    ),
                }
            )


def _write_reference_csv(
    *,
    path: Path,
    observations: list[EcbObservation],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
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

        for observation in observations:
            eur_per_unit = (
                Decimal(1)
                / observation.units_per_eur
            ).quantize(
                Decimal("0.00000001"),
                rounding=ROUND_HALF_UP,
            )

            writer.writerow(
                {
                    "rate_date": (
                        observation
                        .rate_date
                        .isoformat()
                    ),
                    "currency": (
                        observation.currency
                    ),
                    "eur_per_unit": format(
                        eur_per_unit,
                        ".8f",
                    ),
                }
            )


def extract_ecb_rates(
    *,
    start_date: date,
    end_date: date,
    mode: EcbMode,
    lookback_days: int = 7,
    raw_output: str | Path | None = None,
    reference_output: str | Path | None = None,
) -> EcbExtractionResult:
    if end_date < start_date:
        raise ValueError(
            "end_date cannot be before start_date"
        )

    if lookback_days < 0:
        raise ValueError(
            "lookback_days cannot be negative"
        )

    effective_start = (
        start_date
        - timedelta(
            days=lookback_days
        )
    )

    if mode == EcbMode.API:
        observations = (
            fetch_api_observations(
                start_date=effective_start,
                end_date=end_date,
            )
        )

    elif mode == EcbMode.FIXTURE:
        observations = [
            observation
            for observation
            in read_raw_csv(
                RAW_FIXTURE
            )
            if (
                effective_start
                <= observation.rate_date
                <= end_date
            )
        ]

        observations = (
            _validate_observations(
                observations
            )
        )

    else:
        raise ValueError(
            f"Unsupported ECB mode: {mode}"
        )

    suffix = (
        f"{effective_start.isoformat()}_"
        f"{end_date.isoformat()}_"
        f"{mode.value}"
    )

    if raw_output is None:
        raw_path = (
            PROJECT_ROOT
            / "data"
            / "external"
            / "ecb"
            / f"raw_ecb_{suffix}.csv"
        )
    else:
        raw_path = resolve_project_path(
            raw_output
        )

    if reference_output is None:
        reference_path = (
            PROJECT_ROOT
            / "data"
            / "external"
            / "ecb"
            / f"reference_ecb_{suffix}.csv"
        )
    else:
        reference_path = (
            resolve_project_path(
                reference_output
            )
        )

    _write_raw_csv(
        path=raw_path,
        observations=observations,
    )

    _write_reference_csv(
        path=reference_path,
        observations=observations,
    )

    return EcbExtractionResult(
        raw_path=raw_path,
        reference_path=reference_path,
        row_count=len(
            observations
        ),
        effective_start_date=(
            effective_start
        ),
        end_date=end_date,
    )