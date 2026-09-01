from __future__ import annotations

import subprocess
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from airflow.sdk import (
    dag,
    task,
)


PROJECT_ROOT = Path(
    "/opt/airflow/project"
)

FINANCE_RECON_RUNNER = (
    PROJECT_ROOT
    / "airflow"
    / "run_finance_recon.py"
)

CLEAN_CONFIG = (
    "generator/config.example.yml"
)

CLEAN_RUN_DIR = (
    "data/generated/"
    "SYN-42-2026-01-01-"
    "2026-01-31-clean"
)

ECB_RAW_FIXTURE = (
    "generator/fixtures/"
    "ecb_raw_ci_rates.csv"
)


def run_finance_recon(
    *arguments: str,
) -> None:
    subprocess.run(
        [
            "python",
            str(
                FINANCE_RECON_RUNNER
            ),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


@dag(
    dag_id=(
        "finance_reconciliation_ingestion"
    ),
    description=(
        "Generate deterministic Finance "
        "sources and load private-system "
        "and ECB data into RAW PostgreSQL."
    ),
    schedule=None,
    start_date=datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "finance-data",
        "retries": 2,
        "retry_delay": timedelta(
            minutes=1
        ),
    },
    tags=[
        "finance",
        "reconciliation",
        "ingestion",
        "m6",
    ],
)
def finance_reconciliation_ingestion():
    @task()
    def generate_private_sources() -> None:
        run_finance_recon(
            "generate",
            "--config",
            CLEAN_CONFIG,
        )

    @task()
    def load_private_raw() -> None:
        run_finance_recon(
            "load",
            "--run-dir",
            CLEAN_RUN_DIR,
        )

    @task()
    def load_ecb_reference_raw() -> None:
        run_finance_recon(
            "ecb-load",
            "--input",
            ECB_RAW_FIXTURE,
        )

    @task()
    def ingestion_complete() -> None:
        print(
            "Finance RAW ingestion "
            "completed successfully."
        )

    generated = (
        generate_private_sources()
    )

    private_raw = (
        load_private_raw()
    )

    ecb_raw = (
        load_ecb_reference_raw()
    )

    completed = (
        ingestion_complete()
    )

    generated >> private_raw

    [
        private_raw,
        ecb_raw,
    ] >> completed


finance_reconciliation_ingestion()