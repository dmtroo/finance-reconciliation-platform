from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from finance_reconciliation.ecb.extractor import (
    read_raw_csv,
)
from finance_reconciliation.ingestion.database import (
    connect,
)
from finance_reconciliation.paths import (
    resolve_project_path,
)


def _file_sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file_handle:
        for chunk in iter(
            lambda: file_handle.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_ecb_extract(
    path: str | Path,
) -> int:
    resolved = resolve_project_path(
        path
    )

    observations = read_raw_csv(
        resolved
    )

    loaded_at = datetime.now(
        UTC
    )

    batch_id = (
        "ECB-"
        + _file_sha256(
            resolved
        )[:16]
    )

    query = """
        insert into raw_ecb.fx_rates (
            rate_date,
            currency,
            units_per_eur,
            _loaded_at,
            _batch_id
        )
        values (
            %s,
            %s,
            %s,
            %s,
            %s
        )
        on conflict (
            rate_date,
            currency
        )
        do update set
            units_per_eur =
                excluded.units_per_eur,
            _loaded_at =
                excluded._loaded_at,
            _batch_id =
                excluded._batch_id
    """

    parameters = [
        (
            observation.rate_date,
            observation.currency,
            observation.units_per_eur,
            loaded_at,
            batch_id,
        )
        for observation
        in observations
    ]

    with connect() as connection, connection.cursor() as cursor:
        cursor.executemany(
            query,
            parameters,
        )

    return len(
        observations
    )