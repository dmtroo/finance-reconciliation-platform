"""Repository-level checks that keep DDL, dbt sources, and generator config aligned."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _assert_weights_sum_to_one(name: str, weights: dict[str, float]) -> None:
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise AssertionError(f"{name} weights must sum to 1.0; got {total}")


def validate_generator_config() -> None:
    schema = json.loads((ROOT / "generator/config.schema.json").read_text(encoding="utf-8"))
    config = _load_yaml(ROOT / "generator/config.example.yml")
    jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    ).validate(config)

    start = date.fromisoformat(config["date_range"]["start"])
    end = date.fromisoformat(config["date_range"]["end"])
    as_of = date.fromisoformat(config["date_range"]["as_of_date"])
    if not start <= end <= as_of:
        raise AssertionError("date_range must satisfy start <= end <= as_of_date")

    behavior = config["behavior"]
    _assert_weights_sum_to_one(
        "payment_method_weights",
        behavior["payments"]["payment_method_weights"],
    )
    _assert_weights_sum_to_one(
        "refund amount_fraction_weights",
        behavior["refunds"]["amount_fraction_weights"],
    )
    _assert_weights_sum_to_one(
        "settlement delay_days_weights",
        behavior["settlements"]["delay_days_weights"],
    )
    _assert_weights_sum_to_one(
        "bank posting_delay_days_weights",
        behavior["bank"]["posting_delay_days_weights"],
    )
    _assert_weights_sum_to_one(
        "accounting posting_delay_days_weights",
        behavior["accounting"]["posting_delay_days_weights"],
    )

    if behavior["refunds"]["min_delay_days"] > behavior["refunds"]["max_delay_days"]:
        raise AssertionError("refund min_delay_days cannot exceed max_delay_days")
    if behavior["chargebacks"]["min_delay_days"] > behavior["chargebacks"]["max_delay_days"]:
        raise AssertionError("chargeback min_delay_days cannot exceed max_delay_days")
    if (
        behavior["settlements"]["psp_fx_spread_bps_min"]
        > behavior["settlements"]["psp_fx_spread_bps_max"]
    ):
        raise AssertionError("PSP FX spread min cannot exceed max")


def validate_catalog() -> None:
    catalog = _load_yaml(ROOT / "generator/catalog.yml")
    products = catalog["products"]
    product_ids = [product["product_id"] for product in products]
    if len(product_ids) != len(set(product_ids)):
        raise AssertionError("product_id values must be unique")
    _assert_weights_sum_to_one(
        "product selection",
        {product["product_id"]: product["selection_weight"] for product in products},
    )


def validate_source_yaml_conventions() -> None:
    source_files = list((ROOT / "dbt/models/staging").rglob("*__sources.yml"))
    if len(source_files) != 5:
        raise AssertionError(f"Expected 5 source YAML files, found {len(source_files)}")

    for path in source_files:
        doc = _load_yaml(path)
        for source in doc["sources"]:
            config = source.get("config", {})
            if config.get("loaded_at_field") != "_loaded_at":
                raise AssertionError(f"{source['name']} must use _loaded_at for freshness")
            if "freshness" not in config:
                raise AssertionError(f"{source['name']} is missing freshness config")

        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s+tests:\s*$", text, flags=re.MULTILINE):
            raise AssertionError(f"Legacy tests: YAML key found in {path}; use data_tests:")


def validate_ddl_against_sources() -> None:
    ddl = (ROOT / "infra/postgres/init/002_create_raw_tables.sql").read_text(
        encoding="utf-8"
    ).lower()
    source_files = list((ROOT / "dbt/models/staging").rglob("*__sources.yml"))

    declared_tables = 0
    for path in source_files:
        doc = _load_yaml(path)
        for source in doc["sources"]:
            schema_name = source["schema"].lower()
            for table in source["tables"]:
                declared_tables += 1
                fq_name = f"{schema_name}.{table['name'].lower()}"
                if f"create table if not exists {fq_name}" not in ddl:
                    raise AssertionError(f"Missing DDL table: {fq_name}")

                # This is intentionally a lightweight presence check, not a SQL parser.
                for column in table.get("columns", []):
                    column_name = column["name"].lower()
                    if not re.search(rf"\b{re.escape(column_name)}\b", ddl):
                        raise AssertionError(f"Missing DDL column: {fq_name}.{column_name}")

    if declared_tables != 10:
        raise AssertionError(f"Expected 10 RAW tables, found {declared_tables}")


def main() -> None:
    validate_generator_config()
    validate_catalog()
    validate_source_yaml_conventions()
    validate_ddl_against_sources()
    print("Contract validation passed.")


if __name__ == "__main__":
    main()
