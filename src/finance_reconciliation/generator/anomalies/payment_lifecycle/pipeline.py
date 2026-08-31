from __future__ import annotations

from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.capture_amount_mismatch import (
    inject_capture_amount_mismatch,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.common import (
    Tables,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.duplicate_capture import (
    inject_duplicate_capture,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.invalid_refund import (
    inject_invalid_refund,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.late_settlement import (
    inject_late_settlement,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.missing_capture import (
    inject_missing_capture,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.missing_settlement import (
    inject_missing_settlement,
)
from finance_reconciliation.generator.anomalies.payment_lifecycle.over_refund import (
    inject_over_refund,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)


def inject_payment_lifecycle_anomalies(
    tables: Tables,
    *,
    state: (
        AnomalyInjectionState
        | None
    ) = None,
) -> list[AnomalyRecord]:
    if state is None:
        state = AnomalyInjectionState()

    start_index = len(
        state.anomalies
    )

    inject_missing_capture(
        tables,
        state=state,
    )

    inject_capture_amount_mismatch(
        tables,
        state=state,
    )

    inject_duplicate_capture(
        tables,
        state=state,
    )

    inject_invalid_refund(
        tables,
        state=state,
    )

    inject_over_refund(
        tables,
        state=state,
    )

    inject_missing_settlement(
        tables,
        state=state,
    )

    inject_late_settlement(
        tables,
        state=state,
    )

    return state.anomalies[
        start_index:
    ]