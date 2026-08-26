from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from finance_reconciliation.ecb.extractor import (
    EcbMode,
    extract_ecb_rates,
)
from finance_reconciliation.ecb.loader import (
    load_ecb_extract,
)
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

def parse_iso_date(
    value: str,
    *,
    option_name: str,
) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"{option_name} must use YYYY-MM-DD format; got {value!r}"
        ) from exc

@app.command("ecb-extract")
def ecb_extract(
    start_date: Annotated[
        str,
        typer.Option(
            "--start-date",
            help="Finance event-window start date in YYYY-MM-DD format.",
        ),
    ],
    end_date: Annotated[
        str,
        typer.Option(
            "--end-date",
            help="Finance event-window end date in YYYY-MM-DD format.",
        ),
    ],
    mode: Annotated[
        EcbMode,
        typer.Option(
            "--mode",
            help=(
                "ECB extraction mode: "
                "fixture or api."
            ),
        ),
    ] = EcbMode.FIXTURE,
    lookback_days: Annotated[
        int,
        typer.Option(
            "--lookback-days",
            help=(
                "Days fetched before start_date "
                "for weekend/holiday as-of FX."
            ),
        ),
    ] = 7,
    raw_output: Annotated[
        Path | None,
        typer.Option(
            "--raw-output",
        ),
    ] = None,
    reference_output: Annotated[
        Path | None,
        typer.Option(
            "--reference-output",
        ),
    ] = None,
) -> None:
    parsed_start_date = parse_iso_date(
        start_date,
        option_name="--start-date",
    )

    parsed_end_date = parse_iso_date(
        end_date,
        option_name="--end-date",
    )

    result = extract_ecb_rates(
        start_date=parsed_start_date,
        end_date=parsed_end_date,
        mode=mode,
        lookback_days=lookback_days,
        raw_output=raw_output,
        reference_output=reference_output,
    )

    typer.echo(
        f"ECB observations: {result.row_count:,}"
    )

    typer.echo(
        f"Raw extract: {result.raw_path}"
    )

    typer.echo(
        "Generator reference cache: "
        f"{result.reference_path}"
    )


@app.command("ecb-load")
def ecb_load(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            help=(
                "Source-oriented ECB CSV "
                "to load into raw_ecb."
            ),
        ),
    ],
) -> None:
    count = load_ecb_extract(
        input_path
    )

    typer.echo(
        f"Loaded {count:,} ECB observations"
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