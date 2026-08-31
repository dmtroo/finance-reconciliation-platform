from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnomalyRecord:
    anomaly_code: str
    source_table: str
    entity_id: str
    field_name: str | None
    clean_value: Any
    anomalous_value: Any