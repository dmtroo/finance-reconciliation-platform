from __future__ import annotations

import subprocess
import sys
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from pathlib import Path

from airflow.sdk import (
    dag,
    task,
)

PROJECT_ROOT = Path(
    "/opt/airflow/project"
)

AIRFLOW_RUNTIME_ROOT = (
    PROJECT_ROOT
    / "airflow"
)

FINANCE_RECON_RUNNER = (
    AIRFLOW_RUNTIME_ROOT
    / "run_finance_recon.py"
)

DBT_RUNNER = (
    AIRFLOW_RUNTIME_ROOT
    / "run_dbt.py"
)

CLEAN_CONFIG = (
    "generator/config.example.yml"
)

CLEAN_RUN_DIR = (
    "data/generated/"
    "SYN-42-2026-01-01-"
    "2026-01-31-clean"
)


def run_project_script(
    script: Path,
    *arguments: str,
) -> None:
    subprocess.run(
        [
            sys.executable,
            str(script),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )


def run_finance_recon(
    *arguments: str,
) -> None:
    run_project_script(
        FINANCE_RECON_RUNNER,
        *arguments,
    )


def run_dbt(
    *arguments: str,
) -> None:
    run_project_script(
        DBT_RUNNER,
        *arguments,
    )


@dag(
    dag_id=(
        "finance_reconciliation_pipeline"
    ),
    description=(
        "Generate Finance sources, "
        "load RAW data, and build "
        "reconciliation dbt layers."
    ),
    schedule=None,
    start_date=datetime(
        2026,
        1,
        1,
        tzinfo=UTC,
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
        "dbt",
        "m6",
    ],
)
def finance_reconciliation_pipeline():
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
            (
                "generator/fixtures/"
                "ecb_raw_ci_rates.csv"
            ),
        )

    @task()
    def ingestion_complete() -> None:
        print(
            "Finance RAW ingestion "
            "completed successfully."
        )

    @task()
    def dbt_staging() -> None:
        run_dbt(
            "build",
            "--select",
            "path:models/staging",
            "--indirect-selection=buildable",
        )

    @task()
    def dbt_intermediate() -> None:
        run_dbt(
            "build",
            "--select",
            "path:models/intermediate",
            "--indirect-selection=buildable",
        )

    @task()
    def dbt_marts() -> None:
        run_dbt(
            "build",
            "--select",
            "path:models/marts",
            "--indirect-selection=buildable",
        )

    @task()
    def pipeline_complete() -> None:
        print(
            "Finance reconciliation "
            "dbt workflow completed "
            "successfully."
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

    ingested = (
        ingestion_complete()
    )

    staging = (
        dbt_staging()
    )

    intermediate = (
        dbt_intermediate()
    )

    marts = (
        dbt_marts()
    )

    completed = (
        pipeline_complete()
    )

    generated >> private_raw

    [
        private_raw,
        ecb_raw,
    ] >> ingested

    (
        ingested
        >> staging
        >> intermediate
        >> marts
        >> completed
    )


finance_reconciliation_pipeline()