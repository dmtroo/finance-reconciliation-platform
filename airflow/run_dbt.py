from __future__ import annotations

import subprocess
import sys

from runtime_env import (
    build_environment,
    project_root,
)


def run_dbt(
    arguments: list[str],
) -> None:
    if not arguments:
        raise ValueError(
            "dbt command arguments "
            "are required"
        )

    root = project_root()

    dbt_root = (
        root
        / "dbt"
    )

    if not dbt_root.exists():
        raise RuntimeError(
            "dbt project directory "
            "does not exist: "
            f"{dbt_root}"
        )

    environment = build_environment(
        root
    )

    environment[
        "DBT_PROFILES_DIR"
    ] = "."

    subprocess.run(
        [
            "dbt",
            *arguments,
        ],
        cwd=dbt_root,
        env=environment,
        check=True,
    )


def main() -> None:
    run_dbt(
        sys.argv[1:]
    )


if __name__ == "__main__":
    main()