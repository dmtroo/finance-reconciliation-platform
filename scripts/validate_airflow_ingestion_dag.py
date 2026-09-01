from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

DAG_ID = (
    "finance_reconciliation_ingestion"
)

EXPECTED_TASK_IDS = {
    "generate_private_sources",
    "load_private_raw",
    "load_ecb_reference_raw",
    "ingestion_complete",
}


class AirflowDagValidationError(
    RuntimeError
):
    """Raised when the ingestion DAG contract fails."""


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

    if (
        "generate"
        not in result.stdout
        or "load"
        not in result.stdout
    ):
        raise AirflowDagValidationError(
            "finance-recon CLI is not "
            "available in the Airflow "
            "image"
        )

    print(
        "Airflow image: "
        "finance-recon CLI available."
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
        raise AirflowDagValidationError(
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
        raise AirflowDagValidationError(
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
        if isinstance(
            row,
            dict,
        )
        and "dag_id" in row
    }

    if DAG_ID not in dag_ids:
        raise AirflowDagValidationError(
            f"Expected DAG {DAG_ID!r} "
            "was not discovered"
        )

    print(
        f"Airflow DAG discovered: "
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

        raise AirflowDagValidationError(
            "Ingestion DAG task contract "
            "does not match. "
            f"Missing={missing}, "
            f"unexpected={unexpected}"
        )

    print(
        "Airflow ingestion tasks: "
        "4/4 expected tasks found."
    )


def validate_airflow_ingestion_dag(
    *,
    compose_file: Path,
) -> None:
    if not compose_file.exists():
        raise AirflowDagValidationError(
            "Compose file does not exist: "
            f"{compose_file}"
        )

    validate_finance_cli(
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
        "Airflow ingestion DAG "
        "validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the M6 Airflow "
            "Finance ingestion DAG."
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

    validate_airflow_ingestion_dag(
        compose_file=(
            args.compose_file
        )
    )


if __name__ == "__main__":
    main()