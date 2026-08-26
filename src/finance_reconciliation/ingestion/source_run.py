from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from finance_reconciliation.ingestion.specs import (
    TABLE_SPECS,
    TableSpec,
)
from finance_reconciliation.paths import (
    resolve_project_path,
)


@dataclass(frozen=True)
class SourceRun:
    run_dir: Path
    manifest: dict[str, Any]

    @property
    def run_id(self) -> str:
        return str(
            self.manifest["run_id"]
        )

    @property
    def batch_id(self) -> str:
        return (
            f"INGEST-{self.run_id}"
        )


def count_csv_rows(
    path: Path,
) -> int:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        reader = csv.reader(
            file_handle
        )

        next(
            reader,
            None,
        )

        return sum(
            1
            for _ in reader
        )


def validate_header(
    *,
    path: Path,
    spec: TableSpec,
) -> None:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file_handle:
        reader = csv.reader(
            file_handle
        )

        header = next(
            reader,
            None,
        )

    expected = [
        column.name
        for column in spec.columns
    ]

    if header != expected:
        raise ValueError(
            f"Unexpected CSV header in {path}. "
            f"Expected {expected}; got {header}"
        )


def load_source_run(
    run_dir: str | Path,
) -> SourceRun:
    resolved = resolve_project_path(
        run_dir
    )

    manifest_path = (
        resolved
        / "_manifest.json"
    )

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing manifest: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    expected_counts = manifest.get(
        "row_counts",
        {},
    )

    for spec in TABLE_SPECS:
        path = (
            resolved
            / spec.relative_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Missing source extract: {path}"
            )

        validate_header(
            path=path,
            spec=spec,
        )

        actual_count = count_csv_rows(
            path
        )

        expected_count = (
            expected_counts.get(
                spec.key
            )
        )

        if expected_count is None:
            raise ValueError(
                f"Manifest is missing row count "
                f"for {spec.key}"
            )

        if actual_count != expected_count:
            raise ValueError(
                f"Row-count mismatch for {spec.key}: "
                f"manifest={expected_count}, "
                f"csv={actual_count}"
            )

    return SourceRun(
        run_dir=resolved,
        manifest=manifest,
    )