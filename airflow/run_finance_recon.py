from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


DEFAULT_PROJECT_ROOT = Path(
    "/opt/airflow/project"
)

DEFAULT_CONTAINER_HOST = (
    "host.docker.internal"
)


def project_root() -> Path:
    return Path(
        os.environ.get(
            "FINANCE_RECON_PROJECT_ROOT",
            str(DEFAULT_PROJECT_ROOT),
        )
    )


def container_host() -> str:
    return os.environ.get(
        "FINANCE_RECON_CONTAINER_HOST",
        DEFAULT_CONTAINER_HOST,
    )


def is_database_environment_key(
    key: str,
) -> bool:
    normalized = key.upper()

    return any(
        token in normalized
        for token in (
            "DATABASE",
            "POSTGRES",
            "DB_",
            "_DB",
        )
    )


def adapt_database_value(
    *,
    key: str,
    value: str,
) -> str:
    if not is_database_environment_key(
        key
    ):
        return value

    target_host = container_host()

    if (
        "HOST" in key.upper()
        and value
        in {
            "localhost",
            "127.0.0.1",
        }
    ):
        return target_host

    return (
        value
        .replace(
            "@localhost:",
            f"@{target_host}:",
        )
        .replace(
            "@127.0.0.1:",
            f"@{target_host}:",
        )
        .replace(
            "//localhost:",
            f"//{target_host}:",
        )
        .replace(
            "//127.0.0.1:",
            f"//{target_host}:",
        )
    )


def build_environment(
    root: Path,
) -> dict[str, str]:
    environment = dict(
        os.environ
    )

    env_path = (
        root
        / ".env"
    )

    if not env_path.exists():
        return environment

    dotenv_environment = (
        dotenv_values(
            env_path
        )
    )

    for key, raw_value in (
        dotenv_environment.items()
    ):
        if raw_value is None:
            continue

        existing_value = (
            environment.get(
                key,
                raw_value,
            )
        )

        environment[key] = (
            adapt_database_value(
                key=key,
                value=existing_value,
            )
        )

    return environment


def run_finance_recon(
    arguments: list[str],
) -> None:
    if not arguments:
        raise ValueError(
            "finance-recon command "
            "arguments are required"
        )

    root = project_root()

    if not root.exists():
        raise RuntimeError(
            "Finance reconciliation "
            "project root does not exist: "
            f"{root}"
        )

    environment = build_environment(
        root
    )

    subprocess.run(
        [
            "finance-recon",
            *arguments,
        ],
        cwd=root,
        env=environment,
        check=True,
    )


def main() -> None:
    run_finance_recon(
        sys.argv[1:]
    )


if __name__ == "__main__":
    main()