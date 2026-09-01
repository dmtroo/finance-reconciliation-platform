from __future__ import annotations

import subprocess
import sys

from runtime_env import (
    build_environment,
    project_root,
)


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