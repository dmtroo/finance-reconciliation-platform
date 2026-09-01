from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.config import (
    GeneratorConfig,
)

GENERATOR_VERSION = "0.1.0"


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file_handle:
        for chunk in iter(
            lambda: file_handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_effective_config(
    config: GeneratorConfig,
) -> None:
    path = (
        config.output_dir
        / "_effective_config.yml"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        yaml.safe_dump(
            config.data,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_manifest(
    *,
    config: GeneratorConfig,
    row_counts: dict[str, int],
    anomalies: list[AnomalyRecord] | None = None,
) -> None:
    anomaly_records = (
        anomalies
        if anomalies is not None
        else []
    )

    manifest: dict[str, Any] = {
        "generator_version": (
            GENERATOR_VERSION
        ),
        "run_id": config.run_id,
        "seed": config.seed,
        "scenario": config.scenario,
        "date_range": {
            "start": (
                config.start_date.isoformat()
            ),
            "end": (
                config.end_date.isoformat()
            ),
            "as_of_date": (
                config.as_of_date.isoformat()
            ),
        },
        "row_counts": dict(
            sorted(
                row_counts.items()
            )
        ),
        "anomalies": [
            asdict(record)
            for record
            in anomaly_records
        ],
        "config_sha256": (
            sha256_file(
                config.path
            )
        ),
        "catalog_sha256": (
            sha256_file(
                config.catalog_path
            )
        ),
        "fx_reference_sha256": (
            sha256_file(
                config.fx_reference_path
            )
        ),
    }

    path = (
        config.output_dir
        / "_manifest.json"
    )

    path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )