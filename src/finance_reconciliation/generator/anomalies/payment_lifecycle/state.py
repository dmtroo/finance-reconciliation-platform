from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)


@dataclass
class PaymentLifecycleInjectionState:
    anomalies: list[
        AnomalyRecord
    ] = field(
        default_factory=list
    )

    used_invoice_ids: set[
        str
    ] = field(
        default_factory=set
    )

    used_event_ids: set[
        str
    ] = field(
        default_factory=set
    )