from pathlib import Path
from typing import Annotated

import typer

from finance_reconciliation.generator.config import load_config
from finance_reconciliation.generator.manifest import (
    write_effective_config,
    write_manifest,
)
from finance_reconciliation.generator.pipeline import (
    generate_clean_dataset,
    write_clean_dataset,
)

app = typer.Typer(
    help="Finance reconciliation synthetic source generator."
)


@app.callback()
def callback() -> None:
    """Synthetic source generator CLI."""


@app.command()
def generate(
    config_path: Annotated[
        Path,
        typer.Option(
            "--config",
            help="Generator configuration YAML.",
        ),
    ] = Path("generator/config.example.yml"),
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


def main() -> None:
    app()