from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from finance_reconciliation.ingestion.database import connect

DAG_ID = "finance_reconciliation_pipeline"

DEFAULT_COMPOSE_FILE = Path(
    "docker-compose.airflow.yml"
)

DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_POLL_SECONDS = 5

RUNTIME_VALIDATOR = "scripts/validate_airflow_runtime.py"
RECONCILIATION_VALIDATOR = "scripts/validate_m4.py"
REPORT_VALIDATOR = "scripts/validate_finance_report.py"
REPORT_PATH = Path(
    "reports/exports/finance_reconciliation_report.xlsx"
)

TERMINAL_SUCCESS = "success"
TERMINAL_FAILURE = "failed"

# The frozen RAW contract: nine synthetic private-system tables plus the
# single ECB reference table. Each entry is
# (schema, table, source-identity expression) where the identity
# expression is the real PRIMARY KEY from the M0 DDL.
RAW_TABLES: tuple[tuple[str, str, str], ...] = (
    ("raw_billing", "products", "product_id"),
    ("raw_billing", "subscriptions", "subscription_id"),
    ("raw_billing", "invoices", "invoice_id"),
    ("raw_psp", "payment_attempts", "payment_attempt_id"),
    ("raw_psp", "financial_events", "financial_event_id"),
    ("raw_psp", "settlements", "settlement_id"),
    ("raw_psp", "settlement_items", "settlement_item_id"),
    ("raw_bank", "statement_transactions", "bank_transaction_id"),
    ("raw_accounting", "journal_lines", "journal_line_id"),
    ("raw_ecb", "fx_rates", "(rate_date, currency)"),
)


class AirflowWorkflowValidationError(RuntimeError):
    """Raised when the repeated Airflow pipeline run is not operationally safe."""


def compose_prefix(compose_file: Path) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(compose_file),
    ]


def airflow_cli(
    compose_file: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            *compose_prefix(compose_file),
            "exec",
            "-T",
            "airflow-api-server",
            "airflow",
            *arguments,
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def validate_preconditions() -> None:
    result = subprocess.run(
        [sys.executable, RUNTIME_VALIDATOR],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AirflowWorkflowValidationError(
            "Airflow runtime precondition failed:\n"
            f"{result.stdout}{result.stderr}"
        )

    print("Airflow runtime: healthy.")


def unpause_dag(compose_file: Path) -> None:
    airflow_cli(
        compose_file,
        "dags",
        "unpause",
        DAG_ID,
    )


def dag_run_state(
    compose_file: Path,
    *,
    run_id: str,
) -> str | None:
    result = airflow_cli(
        compose_file,
        "dags",
        "state",
        DAG_ID,
        run_id,
        check=False,
    )

    if result.returncode != 0:
        return None

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    if not lines:
        return None

    return lines[-1].lower()


def task_states(
    compose_file: Path,
    *,
    run_id: str,
) -> str:
    result = airflow_cli(
        compose_file,
        "tasks",
        "states-for-dag-run",
        DAG_ID,
        run_id,
        check=False,
    )

    return result.stdout or result.stderr


def trigger_pipeline_run(
    compose_file: Path,
    *,
    run_id: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> None:
    trigger = airflow_cli(
        compose_file,
        "dags",
        "trigger",
        DAG_ID,
        "-r",
        run_id,
        check=False,
    )

    if trigger.returncode != 0:
        raise AirflowWorkflowValidationError(
            "Failed to trigger Airflow pipeline run:\n"
            f"dag_id={DAG_ID}\n"
            f"run_id={run_id}\n"
            f"{trigger.stdout}{trigger.stderr}"
        )

    deadline = time.monotonic() + timeout_seconds
    last_state: str | None = None

    while time.monotonic() < deadline:
        last_state = dag_run_state(
            compose_file,
            run_id=run_id,
        )

        if last_state == TERMINAL_SUCCESS:
            return

        if last_state == TERMINAL_FAILURE:
            raise AirflowWorkflowValidationError(
                "Airflow pipeline run failed:\n"
                f"dag_id={DAG_ID}\n"
                f"run_id={run_id}\n"
                f"state={last_state}\n"
                f"{task_states(compose_file, run_id=run_id)}"
            )

        time.sleep(poll_seconds)

    raise AirflowWorkflowValidationError(
        "Timed out waiting for the Airflow pipeline run:\n"
        f"dag_id={DAG_ID}\n"
        f"run_id={run_id}\n"
        f"last_state={last_state}\n"
        f"{task_states(compose_file, run_id=run_id)}"
    )


def raw_snapshot(cursor) -> dict[str, int]:
    snapshot: dict[str, int] = {}

    for schema, table, _identity in RAW_TABLES:
        cursor.execute(
            f'select count(*) from "{schema}"."{table}"'
        )
        snapshot[f"{schema}.{table}"] = int(
            cursor.fetchone()[0]
        )

    return snapshot


def source_identity_issues(cursor) -> list[str]:
    issues: list[str] = []

    for schema, table, identity in RAW_TABLES:
        cursor.execute(
            f"select count(*), count(distinct {identity}) "
            f'from "{schema}"."{table}"'
        )
        total, distinct = cursor.fetchone()

        if int(total) != int(distinct):
            issues.append(
                f"{schema}.{table}: "
                f"rows={int(total):,}, "
                f"distinct {identity}={int(distinct):,}"
            )

    return issues


def exception_mart_count(
    cursor,
    *,
    analytics_schema: str,
) -> int:
    cursor.execute(
        f'select count(*) from "{analytics_schema}".'
        '"mart_reconciliation_exceptions"'
    )
    return int(cursor.fetchone()[0])


def capture_finance_state(
    *,
    analytics_schema: str,
) -> tuple[dict[str, int], list[str], int]:
    with connect() as connection, connection.cursor() as cursor:
        snapshot = raw_snapshot(cursor)
        identity_issues = source_identity_issues(cursor)
        exceptions = exception_mart_count(
            cursor,
            analytics_schema=analytics_schema,
        )

    return snapshot, identity_issues, exceptions


def run_reconciliation_validator() -> None:
    result = subprocess.run(
        [sys.executable, RECONCILIATION_VALIDATOR],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AirflowWorkflowValidationError(
            "Finance reconciliation validation failed after repeated "
            "Airflow run:\n"
            f"{result.stdout}{result.stderr}"
        )


def run_report_validator() -> None:
    # The DAG's export_finance_report task wrote the workbook (bind mount);
    # reuse the standalone report validator rather than re-checking it here.
    if not REPORT_PATH.exists():
        raise AirflowWorkflowValidationError(
            "Airflow run did not publish the Finance report: "
            f"{REPORT_PATH}"
        )

    # The production DAG always runs the clean pipeline.
    result = subprocess.run(
        [
            sys.executable,
            REPORT_VALIDATOR,
            "--scenario",
            "clean",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise AirflowWorkflowValidationError(
            "Finance report validation failed after repeated "
            "Airflow run:\n"
            f"{result.stdout}{result.stderr}"
        )


def diff_snapshots(
    first: dict[str, int],
    second: dict[str, int],
) -> list[str]:
    diffs: list[str] = []

    for table, first_count in first.items():
        second_count = second[table]

        if first_count != second_count:
            diffs.append(
                f"{table}: "
                f"{first_count:,} -> {second_count:,} "
                f"(difference {second_count - first_count:+,})"
            )

    return diffs


def validate_airflow_workflow(
    *,
    compose_file: Path,
    timeout_seconds: int,
    poll_seconds: int,
    analytics_schema: str,
) -> None:
    if not compose_file.exists():
        raise AirflowWorkflowValidationError(
            f"Compose file does not exist: {compose_file}"
        )

    validate_preconditions()
    unpause_dag(compose_file)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    run_id_1 = f"m6_workflow__{stamp}__1"
    run_id_2 = f"m6_workflow__{stamp}__2"

    trigger_pipeline_run(
        compose_file,
        run_id=run_id_1,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    print("Airflow pipeline run 1: success.")

    snapshot_1, identity_1, exceptions_1 = capture_finance_state(
        analytics_schema=analytics_schema,
    )
    print(
        f"RAW snapshot after run 1: {len(snapshot_1)} tables captured."
    )
    print()

    trigger_pipeline_run(
        compose_file,
        run_id=run_id_2,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )
    print("Airflow pipeline run 2: success.")

    snapshot_2, identity_2, exceptions_2 = capture_finance_state(
        analytics_schema=analytics_schema,
    )
    print(
        f"RAW snapshot after run 2: {len(snapshot_2)} tables captured."
    )
    print()

    diffs = diff_snapshots(snapshot_1, snapshot_2)
    if diffs:
        raise AirflowWorkflowValidationError(
            "RAW idempotency failed:\n" + "\n".join(diffs)
        )
    print("RAW idempotency: row counts unchanged.")

    identity_issues = identity_1 + identity_2
    if identity_issues:
        raise AirflowWorkflowValidationError(
            "RAW source identity failed:\n"
            + "\n".join(identity_issues)
        )
    print("RAW source identity: uniqueness checks passed.")

    if exceptions_1 != 0 or exceptions_2 != 0:
        raise AirflowWorkflowValidationError(
            "Clean scenario produced reconciliation exceptions:\n"
            f"after run 1: {exceptions_1:,}\n"
            f"after run 2: {exceptions_2:,}"
        )

    run_reconciliation_validator()
    print("Clean reconciliation validation: passed.")

    run_report_validator()
    print("Finance report: matches the marts after the repeated run.")

    print()
    print("Airflow reconciliation workflow validation passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that the M6 Airflow reconciliation pipeline can "
            "run twice without corrupting Finance data."
        )
    )

    parser.add_argument(
        "--compose-file",
        type=Path,
        default=DEFAULT_COMPOSE_FILE,
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Maximum time to wait for a single triggered DAG run."
        ),
    )

    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=DEFAULT_POLL_SECONDS,
        help="Interval between DAG-run state checks.",
    )

    parser.add_argument(
        "--analytics-schema",
        default=os.getenv("DBT_SCHEMA", "analytics_dev"),
        help="Schema that holds the reconciliation marts.",
    )

    args = parser.parse_args()

    validate_airflow_workflow(
        compose_file=args.compose_file,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
        analytics_schema=args.analytics_schema,
    )


if __name__ == "__main__":
    main()
