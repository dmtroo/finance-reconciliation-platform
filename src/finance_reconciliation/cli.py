from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from finance_reconciliation.generator.config import (
    load_config,
)
from finance_reconciliation.generator.manifest import (
    write_effective_config,
    write_manifest,
)
from finance_reconciliation.generator.pipeline import (
    generate_clean_dataset,
    write_clean_dataset,
)
from finance_reconciliation.ingestion.loader import (
    load_run_directory,
)

app = typer.Typer(
    help=(
        "Finance reconciliation platform "
        "local development CLI."
    )
)


@app.command()
def generate(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            help=(
                "Generator configuration YAML."
            ),
        ),
    ] = Path(
        "generator/config.example.yml"
    ),
) -> None:
    config = load_config(
        config_path
    )

    dataset = generate_clean_dataset(
        config
    )

    counts = write_clean_dataset(
        config=config,
        dataset=dataset,
    )

    write_effective_config(
        config
    )

    write_manifest(
        config=config,
        row_counts=counts,
    )

    typer.echo(
        f"Generated run: {config.run_id}"
    )

    typer.echo(
        f"Output: {config.output_dir}"
    )

    for table, count in counts.items():
        typer.echo(
            f"{table}: {count:,} rows"
        )


@app.command("load")
def load_generated_run(
    run_dir: Annotated[
        Path,
        typer.Option(
            "--run-dir",
            help=(
                "Generated source run directory."
            ),
        ),
    ],
) -> None:
    counts = load_run_directory(
        run_dir
    )

    typer.echo(
        f"Loaded source run: {run_dir}"
    )

    for table, count in counts.items():
        typer.echo(
            f"{table}: {count:,} source rows"
        )


def main() -> None:
    app()