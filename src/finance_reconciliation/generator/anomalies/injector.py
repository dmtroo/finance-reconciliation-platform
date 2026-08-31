from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle import (
    inject_payment_lifecycle_anomalies,
)


@dataclass
class AnomalyInjectionResult:
    tables: dict[
        str,
        list[dict[str, Any]],
    ]
    anomalies: list[
        AnomalyRecord
    ]


def inject_anomalies(
    tables: dict[
        str,
        list[dict[str, Any]],
    ],
) -> AnomalyInjectionResult:
    copied_tables = {
        table_name: [
            dict(row)
            for row in rows
        ]
        for table_name, rows
        in tables.items()
    }

    anomalies = (
        inject_payment_lifecycle_anomalies(
            copied_tables
        )
    )

    return AnomalyInjectionResult(
        tables=copied_tables,
        anomalies=anomalies,
    )