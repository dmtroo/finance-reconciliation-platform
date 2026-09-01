from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

DAG_ID = (
    "finance_reconciliation_pipeline"
)

EXPECTED_TASK_IDS = {
    "generate_private_sources",
    "load_private_raw",
    "load_ecb_reference_raw",
    "ingestion_complete",
    "dbt_staging",
    "dbt_intermediate",
    "dbt_marts",
    "validate_reconciliation",
    "pipeline_complete",
}

# The validate_reconciliation task must run this exact script - the same
# one `make m4-validate` runs - not a second copy of the M4 logic.
RECONCILIATION_VALIDATOR = (
    "/opt/airflow/project/scripts/validate_m4.py"
)


class AirflowPipelineValidationError(
    RuntimeError
):
    """Raised when the Airflow pipeline contract fails."""


def run_command(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def compose_command(
    compose_file: Path,
) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(compose_file),
    ]


def airflow_command(
    compose_file: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            *compose_command(
                compose_file
            ),
            "exec",
            "-T",
            "airflow-api-server",
            "airflow",
            *arguments,
        ]
    )


def validate_finance_cli(
    *,
    compose_file: Path,
) -> None:
    result = run_command(
        [
            *compose_command(
                compose_file
            ),
            "exec",
            "-T",
            "airflow-api-server",
            "finance-recon",
            "--help",
        ]
    )

    required_commands = {
        "generate",
        "load",
        "ecb-load",
    }

    missing = {
        command
        for command
        in required_commands
        if command
        not in result.stdout
    }

    if missing:
        raise AirflowPipelineValidationError(
            "finance-recon CLI is "
            "missing required commands: "
            f"{sorted(missing)}"
        )

    print(
        "Airflow image: "
        "finance-recon CLI available."
    )


def validate_dbt_cli(
    *,
    compose_file: Path,
) -> None:
    result = run_command(
        [
            *compose_command(
                compose_file
            ),
            "exec",
            "-T",
            "airflow-api-server",
            "dbt",
            "--version",
        ]
    )

    output = result.stdout

    if (
        "Core:" not in output
        or "postgres" not in output.lower()
    ):
        raise AirflowPipelineValidationError(
            "dbt Core with PostgreSQL "
            "adapter is not available "
            "in the Airflow image"
        )

    print(
        "Airflow image: "
        "dbt Core and PostgreSQL "
        "adapter available."
    )


def validate_reconciliation_validator(
    *,
    compose_file: Path,
) -> None:
    # Import validate_m4.py inside the Airflow image without executing it,
    # so we know the same clean-reconciliation validator the DAG's
    # validate_reconciliation task shells out to is present and all of
    # its imports (finance_reconciliation, psycopg, dotenv, yaml)
    # resolve there.
    snippet = (
        "import importlib.util as u, pathlib; "
        f"p = pathlib.Path({RECONCILIATION_VALIDATOR!r}); "
        "assert p.is_file(), 'validate_m4.py is missing'; "
        "spec = u.spec_from_file_location('m4_validator', p); "
        "mod = u.module_from_spec(spec); "
        "spec.loader.exec_module(mod); "
        "assert callable(getattr(mod, 'validate_m4', None)), "
        "'validate_m4() is not defined'; "
        "print('ok')"
    )

    result = run_command(
        [
            *compose_command(
                compose_file
            ),
            "exec",
            "-T",
            "airflow-api-server",
            "python",
            "-c",
            snippet,
        ]
    )

    if "ok" not in result.stdout:
        raise AirflowPipelineValidationError(
            "clean Finance reconciliation "
            "validator is not importable "
            "in the Airflow image"
        )

    print(
        "Airflow image: "
        "clean reconciliation (M4) "
        "validator available."
    )


def load_json_output(
    output: str,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            output
        )
    except json.JSONDecodeError as exc:
        raise AirflowPipelineValidationError(
            f"{label} did not return "
            "valid JSON"
        ) from exc


def validate_import_errors(
    *,
    compose_file: Path,
) -> None:
    result = airflow_command(
        compose_file,
        "dags",
        "list-import-errors",
        "-l",
        "-o",
        "json",
    )

    errors = load_json_output(
        result.stdout,
        label=(
            "Airflow import-error list"
        ),
    )

    if errors:
        raise AirflowPipelineValidationError(
            "Airflow DAG import errors "
            f"found: {errors}"
        )

    print(
        "Airflow DAG imports: clean."
    )


def validate_dag_exists(
    *,
    compose_file: Path,
) -> None:
    result = airflow_command(
        compose_file,
        "dags",
        "list",
        "-l",
        "-o",
        "json",
    )

    dags = load_json_output(
        result.stdout,
        label="Airflow DAG list",
    )

    dag_ids = {
        str(
            row["dag_id"]
        )
        for row in dags
        if (
            isinstance(
                row,
                dict,
            )
            and "dag_id" in row
        )
    }

    if DAG_ID not in dag_ids:
        raise AirflowPipelineValidationError(
            f"Expected DAG {DAG_ID!r} "
            "was not discovered"
        )

    print(
        "Airflow DAG discovered: "
        f"{DAG_ID}."
    )


def validate_task_contract(
    *,
    compose_file: Path,
) -> None:
    result = airflow_command(
        compose_file,
        "tasks",
        "list",
        DAG_ID,
    )

    task_ids = {
        line.strip()
        for line
        in result.stdout.splitlines()
        if line.strip()
    }

    if (
        task_ids
        != EXPECTED_TASK_IDS
    ):
        missing = sorted(
            EXPECTED_TASK_IDS
            - task_ids
        )

        unexpected = sorted(
            task_ids
            - EXPECTED_TASK_IDS
        )

        raise AirflowPipelineValidationError(
            "Airflow pipeline task "
            "contract does not match. "
            f"Missing={missing}, "
            f"unexpected={unexpected}"
        )

    print(
        "Airflow pipeline tasks: "
        f"{len(EXPECTED_TASK_IDS)}/"
        f"{len(EXPECTED_TASK_IDS)} "
        "expected tasks found."
    )


def validate_airflow_pipeline(
    *,
    compose_file: Path,
) -> None:
    if not compose_file.exists():
        raise AirflowPipelineValidationError(
            "Compose file does not exist: "
            f"{compose_file}"
        )

    validate_finance_cli(
        compose_file=compose_file
    )

    validate_dbt_cli(
        compose_file=compose_file
    )

    validate_reconciliation_validator(
        compose_file=compose_file
    )

    validate_import_errors(
        compose_file=compose_file
    )

    validate_dag_exists(
        compose_file=compose_file
    )

    validate_task_contract(
        compose_file=compose_file
    )

    print(
        "Airflow reconciliation pipeline "
        "validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the M6 Airflow "
            "Finance reconciliation "
            "pipeline DAG."
        )
    )

    parser.add_argument(
        "--compose-file",
        type=Path,
        default=Path(
            "docker-compose.airflow.yml"
        ),
    )

    args = parser.parse_args()

    validate_airflow_pipeline(
        compose_file=(
            args.compose_file
        )
    )


if __name__ == "__main__":
    main()