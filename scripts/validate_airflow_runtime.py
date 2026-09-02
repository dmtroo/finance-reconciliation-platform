from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

# `airflow jobs check` reads the job's last heartbeat; under DAG-parse
# load it can be momentarily stale even on a healthy service, so retry
# briefly before failing.
JOB_CHECK_ATTEMPTS = 6
JOB_CHECK_DELAY_SECONDS = 5

EXPECTED_RUNNING_SERVICES = {
    "airflow-postgres",
    "airflow-api-server",
    "airflow-scheduler",
    "airflow-dag-processor",
}


class AirflowRuntimeValidationError(
    RuntimeError
):
    """Raised when the local Airflow runtime is unhealthy."""


def run_command(
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def run_job_check(
    command: list[str],
) -> None:
    last_error: subprocess.CalledProcessError | None = None

    for attempt in range(JOB_CHECK_ATTEMPTS):
        try:
            run_command(command)
            return
        except subprocess.CalledProcessError as error:
            last_error = error

            if attempt < JOB_CHECK_ATTEMPTS - 1:
                time.sleep(JOB_CHECK_DELAY_SECONDS)

    raise AirflowRuntimeValidationError(
        "Airflow job heartbeat check failed after "
        f"{JOB_CHECK_ATTEMPTS} attempts: "
        f"{last_error.stdout if last_error else ''}"
        f"{last_error.stderr if last_error else ''}"
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


def validate_running_services(
    *,
    compose_file: Path,
) -> None:
    command = [
        *compose_command(
            compose_file
        ),
        "ps",
        "--services",
        "--status",
        "running",
    ]

    result = run_command(
        command
    )

    running_services = {
        line.strip()
        for line
        in result.stdout.splitlines()
        if line.strip()
    }

    missing = (
        EXPECTED_RUNNING_SERVICES
        - running_services
    )

    if missing:
        raise AirflowRuntimeValidationError(
            "Airflow services are not "
            "running: "
            f"{sorted(missing)}"
        )

    print(
        "Airflow services: "
        "all required services running."
    )


def validate_airflow_version(
    *,
    compose_file: Path,
) -> None:
    command = [
        *compose_command(
            compose_file
        ),
        "exec",
        "-T",
        "airflow-api-server",
        "airflow",
        "version",
    ]

    result = run_command(
        command
    )

    version = (
        result.stdout.strip()
    )

    if not version:
        raise AirflowRuntimeValidationError(
            "Airflow version command "
            "returned no output"
        )

    print(
        f"Airflow version: {version}"
    )


def validate_scheduler(
    *,
    compose_file: Path,
) -> None:
    command = [
        *compose_command(
            compose_file
        ),
        "exec",
        "-T",
        "airflow-scheduler",
        "bash",
        "-lc",
        (
            "airflow jobs check "
            "--job-type SchedulerJob "
            '--hostname "$HOSTNAME"'
        ),
    ]

    run_job_check(
        command
    )

    print(
        "Airflow scheduler: healthy."
    )


def validate_dag_processor(
    *,
    compose_file: Path,
) -> None:
    command = [
        *compose_command(
            compose_file
        ),
        "exec",
        "-T",
        "airflow-dag-processor",
        "bash",
        "-lc",
        (
            "airflow jobs check "
            "--job-type DagProcessorJob "
            '--hostname "$HOSTNAME"'
        ),
    ]

    run_job_check(
        command
    )

    print(
        "Airflow DAG processor: healthy."
    )


def validate_api_server(
    *,
    url: str,
) -> None:
    with urlopen(
        url,
        timeout=10,
    ) as response:
        status_code = (
            response.status
        )

    if status_code != 200:
        raise AirflowRuntimeValidationError(
            "Airflow API health endpoint "
            "returned HTTP "
            f"{status_code}"
        )

    print(
        "Airflow API server: healthy."
    )


def validate_airflow_runtime(
    *,
    compose_file: Path,
    api_health_url: str,
) -> None:
    if not compose_file.exists():
        raise AirflowRuntimeValidationError(
            "Airflow compose file does "
            f"not exist: {compose_file}"
        )

    validate_running_services(
        compose_file=compose_file
    )

    validate_airflow_version(
        compose_file=compose_file
    )

    validate_scheduler(
        compose_file=compose_file
    )

    validate_dag_processor(
        compose_file=compose_file
    )

    validate_api_server(
        url=api_health_url
    )

    print(
        "Airflow runtime validation passed."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the local Airflow "
            "runtime for M6."
        )
    )

    parser.add_argument(
        "--compose-file",
        type=Path,
        default=Path(
            "docker-compose.airflow.yml"
        ),
    )

    parser.add_argument(
        "--api-health-url",
        default=(
            "http://localhost:8081/"
            "api/v2/monitor/health"
        ),
    )

    args = parser.parse_args()

    validate_airflow_runtime(
        compose_file=(
            args.compose_file
        ),
        api_health_url=(
            args.api_health_url
        ),
    )


if __name__ == "__main__":
    main()