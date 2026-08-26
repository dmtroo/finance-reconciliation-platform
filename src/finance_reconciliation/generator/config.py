from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class GeneratorConfig:
    """Validated generator configuration and its source path."""

    path: Path
    data: dict[str, Any]

    @property
    def seed(self) -> int:
        return int(self.data["seed"])

    @property
    def scenario(self) -> str:
        return str(self.data["scenario"])

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.data["date_range"]["start"])

    @property
    def end_date(self) -> date:
        return date.fromisoformat(self.data["date_range"]["end"])

    @property
    def as_of_date(self) -> date:
        return date.fromisoformat(self.data["date_range"]["as_of_date"])

    @property
    def run_id(self) -> str:
        return (
            f"SYN-{self.seed}-"
            f"{self.start_date.isoformat()}-"
            f"{self.end_date.isoformat()}-"
            f"{self.scenario}"
        )

    @property
    def output_root(self) -> Path:
        return resolve_project_path(self.data["output"]["root"])

    @property
    def output_dir(self) -> Path:
        return self.output_root / self.run_id

    @property
    def catalog_path(self) -> Path:
        return resolve_project_path(self.data["catalog"]["path"])

    @property
    def fx_reference_path(self) -> Path:
        return resolve_project_path(self.data["fx_reference"]["path"])


def resolve_project_path(value: str | Path) -> Path:
    """Resolve a repository-relative path without depending on current shell directory."""

    path = Path(value)

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise TypeError(f"Expected a YAML mapping in {path}")

    return data


def _validate_semantics(data: dict[str, Any]) -> None:
    start = date.fromisoformat(data["date_range"]["start"])
    end = date.fromisoformat(data["date_range"]["end"])
    as_of = date.fromisoformat(data["date_range"]["as_of_date"])

    if not start <= end <= as_of:
        raise ValueError(
            "date_range must satisfy start <= end <= as_of_date"
        )

    subscriptions = data["behavior"]["subscriptions"]

    if (
        subscriptions["cancelled_rate"]
        + subscriptions["past_due_rate"]
        > 1
    ):
        raise ValueError(
            "cancelled_rate + past_due_rate cannot exceed 1"
        )

    refunds = data["behavior"]["refunds"]

    if refunds["min_delay_days"] > refunds["max_delay_days"]:
        raise ValueError(
            "refund min_delay_days cannot exceed max_delay_days"
        )

    chargebacks = data["behavior"]["chargebacks"]

    if chargebacks["min_delay_days"] > chargebacks["max_delay_days"]:
        raise ValueError(
            "chargeback min_delay_days cannot exceed max_delay_days"
        )

    settlements = data["behavior"]["settlements"]

    if (
        settlements["psp_fx_spread_bps_min"]
        > settlements["psp_fx_spread_bps_max"]
    ):
        raise ValueError(
            "PSP FX spread min cannot exceed max"
        )


def load_config(
    path: str | Path = "generator/config.example.yml",
) -> GeneratorConfig:
    """Load and validate a generator configuration."""

    config_path = resolve_project_path(path)
    schema_path = PROJECT_ROOT / "generator" / "config.schema.json"

    data = _load_yaml(config_path)

    schema = json.loads(
        schema_path.read_text(encoding="utf-8")
    )

    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(data)

    _validate_semantics(data)

    return GeneratorConfig(
        path=config_path,
        data=data,
    )