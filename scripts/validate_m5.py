from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_TABLES = {
    "billing/products",
    "billing/subscriptions",
    "billing/invoices",
    "psp/payment_attempts",
    "psp/financial_events",
    "psp/settlements",
    "psp/settlement_items",
    "bank/statement_transactions",
    "accounting/journal_lines",
}


EXPECTED_ANOMALY_CODES = [
    "MISSING_CAPTURE",
    "CAPTURE_AMOUNT_MISMATCH",
    "DUPLICATE_CAPTURE",
    "INVALID_REFUND",
    "OVER_REFUND",
    "MISSING_SETTLEMENT",
    "LATE_SETTLEMENT",
    "SETTLEMENT_TOTAL_MISMATCH",
    "MISSING_BANK_RECEIPT",
    "BANK_AMOUNT_MISMATCH",
    "MISSING_LEDGER_POSTING",
    "LEDGER_AMOUNT_MISMATCH",
    "UNBALANCED_JOURNAL",
    "MISSING_FX_RATE",
    "FX_RATE_OUTLIER",
    "UNMAPPED_PRODUCT",
]


class M5ValidationError(
    RuntimeError
):
    """Raised when the M5 scenario contract fails."""


def load_manifest(
    run_dir: Path,
) -> dict[str, Any]:
    path = (
        run_dir
        / "_manifest.json"
    )

    if not path.exists():
        raise M5ValidationError(
            "Generated run manifest does "
            f"not exist: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        manifest = json.load(
            handle
        )

    if not isinstance(
        manifest,
        dict,
    ):
        raise M5ValidationError(
            "Generated run manifest "
            "must be a JSON object"
        )

    return manifest


def manifest_row_counts(
    manifest: dict[str, Any],
    *,
    label: str,
) -> dict[str, int]:
    raw_counts = manifest.get(
        "row_counts"
    )

    if not isinstance(
        raw_counts,
        dict,
    ):
        raise M5ValidationError(
            f"{label} manifest does not "
            "contain row_counts"
        )

    counts = {
        str(table): int(count)
        for table, count
        in raw_counts.items()
    }

    actual_tables = set(
        counts
    )

    if (
        actual_tables
        != EXPECTED_TABLES
    ):
        missing = sorted(
            EXPECTED_TABLES
            - actual_tables
        )

        unexpected = sorted(
            actual_tables
            - EXPECTED_TABLES
        )

        raise M5ValidationError(
            f"{label} table contract "
            "does not match the nine "
            "private source tables. "
            f"Missing={missing}, "
            f"unexpected={unexpected}"
        )

    for table, count in counts.items():
        if count < 0:
            raise M5ValidationError(
                f"{label} has negative "
                f"row count for {table}: "
                f"{count}"
            )

    return counts


def manifest_anomalies(
    manifest: dict[str, Any],
    *,
    label: str,
) -> list[dict[str, Any]]:
    raw_anomalies = manifest.get(
        "anomalies"
    )

    if not isinstance(
        raw_anomalies,
        list,
    ):
        raise M5ValidationError(
            f"{label} manifest does not "
            "contain an anomalies list"
        )

    anomalies: list[
        dict[str, Any]
    ] = []

    for index, record in enumerate(
        raw_anomalies
    ):
        if not isinstance(
            record,
            dict,
        ):
            raise M5ValidationError(
                f"{label} anomaly "
                f"record {index} is not "
                "an object"
            )

        anomalies.append(
            record
        )

    return anomalies


def validate_clean_manifest(
    manifest: dict[str, Any],
) -> dict[str, int]:
    scenario = manifest.get(
        "scenario"
    )

    if scenario != "clean":
        raise M5ValidationError(
            "Clean manifest scenario "
            f"must be 'clean', found "
            f"{scenario!r}"
        )

    anomalies = manifest_anomalies(
        manifest,
        label="Clean",
    )

    if anomalies:
        raise M5ValidationError(
            "Clean scenario must contain "
            "zero injected anomalies, "
            f"found {len(anomalies)}"
        )

    counts = manifest_row_counts(
        manifest,
        label="Clean",
    )

    print(
        "Clean manifest: "
        "scenario=clean, anomalies=0."
    )

    return counts


def validate_anomaly_record(
    record: dict[str, Any],
    *,
    index: int,
) -> None:
    required_fields = {
        "anomaly_code",
        "source_table",
        "entity_id",
        "field_name",
        "clean_value",
        "anomalous_value",
    }

    missing = sorted(
        required_fields
        - set(record)
    )

    if missing:
        raise M5ValidationError(
            "Anomaly record "
            f"{index} is missing "
            f"fields: {missing}"
        )

    for field in (
        "anomaly_code",
        "source_table",
        "entity_id",
        "field_name",
    ):
        value = record[field]

        if (
            not isinstance(
                value,
                str,
            )
            or not value
        ):
            raise M5ValidationError(
                "Anomaly record "
                f"{index} has invalid "
                f"{field}: {value!r}"
            )

    if (
        record["clean_value"]
        == record["anomalous_value"]
    ):
        raise M5ValidationError(
            "Anomaly record "
            f"{index} does not actually "
            "change its recorded value"
        )


def validate_anomaly_manifest(
    manifest: dict[str, Any],
) -> dict[str, int]:
    scenario = manifest.get(
        "scenario"
    )

    if (
        scenario
        != "with_anomalies"
    ):
        raise M5ValidationError(
            "Anomaly manifest scenario "
            "must be 'with_anomalies', "
            f"found {scenario!r}"
        )

    anomalies = manifest_anomalies(
        manifest,
        label="With-anomalies",
    )

    if (
        len(anomalies)
        != len(
            EXPECTED_ANOMALY_CODES
        )
    ):
        raise M5ValidationError(
            "With-anomalies scenario "
            "must contain exactly "
            f"{len(EXPECTED_ANOMALY_CODES)} "
            "injections, found "
            f"{len(anomalies)}"
        )

    for index, record in enumerate(
        anomalies
    ):
        validate_anomaly_record(
            record,
            index=index,
        )

    actual_codes = [
        str(
            record[
                "anomaly_code"
            ]
        )
        for record in anomalies
    ]

    if (
        actual_codes
        != EXPECTED_ANOMALY_CODES
    ):
        raise M5ValidationError(
            "Anomaly injection order "
            "does not match the frozen "
            "M5 contract. "
            f"Actual={actual_codes}"
        )

    entity_keys = [
        (
            str(
                record[
                    "anomaly_code"
                ]
            ),
            str(
                record[
                    "entity_id"
                ]
            ),
        )
        for record in anomalies
    ]

    if (
        len(entity_keys)
        != len(set(entity_keys))
    ):
        raise M5ValidationError(
            "Duplicate anomaly-code/"
            "entity combinations found "
            "in anomaly manifest"
        )

    counts = manifest_row_counts(
        manifest,
        label="With-anomalies",
    )

    print(
        "Anomaly manifest: "
        "scenario=with_anomalies, "
        "16 frozen injections."
    )

    return counts


def validate_equal_row_counts(
    *,
    clean_counts: dict[str, int],
    anomaly_counts: dict[str, int],
) -> None:
    if (
        clean_counts
        != anomaly_counts
    ):
        differences = {}

        for table in sorted(
            EXPECTED_TABLES
        ):
            clean_count = (
                clean_counts[
                    table
                ]
            )

            anomaly_count = (
                anomaly_counts[
                    table
                ]
            )

            if (
                clean_count
                != anomaly_count
            ):
                differences[
                    table
                ] = {
                    "clean": (
                        clean_count
                    ),
                    "with_anomalies": (
                        anomaly_count
                    ),
                }

        raise M5ValidationError(
            "Clean and with-anomalies "
            "row counts differ. "
            f"Differences={differences}"
        )

    print(
        "Scenario row counts: "
        "clean and with_anomalies "
        "match for all nine tables."
    )


def print_row_counts(
    counts: dict[str, int],
) -> None:
    print(
        "Source row counts:"
    )

    for table in sorted(
        counts
    ):
        print(
            f"  {table}: "
            f"{counts[table]:,}"
        )


def validate_m5(
    *,
    clean_run_dir: Path,
    anomaly_run_dir: Path,
) -> None:
    clean_manifest = (
        load_manifest(
            clean_run_dir
        )
    )

    anomaly_manifest = (
        load_manifest(
            anomaly_run_dir
        )
    )

    clean_counts = (
        validate_clean_manifest(
            clean_manifest
        )
    )

    anomaly_counts = (
        validate_anomaly_manifest(
            anomaly_manifest
        )
    )

    validate_equal_row_counts(
        clean_counts=clean_counts,
        anomaly_counts=(
            anomaly_counts
        ),
    )

    print_row_counts(
        clean_counts
    )

    print(
        "M5 scenario validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate deterministic "
            "clean and with_anomalies "
            "generator scenarios for M5."
        )
    )

    parser.add_argument(
        "--clean-run-dir",
        required=True,
        type=Path,
        help=(
            "Generated clean source "
            "run directory."
        ),
    )

    parser.add_argument(
        "--anomaly-run-dir",
        required=True,
        type=Path,
        help=(
            "Generated with_anomalies "
            "source run directory."
        ),
    )

    args = parser.parse_args()

    validate_m5(
        clean_run_dir=(
            args.clean_run_dir
        ),
        anomaly_run_dir=(
            args.anomaly_run_dir
        ),
    )


if __name__ == "__main__":
    main()