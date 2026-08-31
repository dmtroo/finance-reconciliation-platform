from __future__ import annotations

from finance_reconciliation.generator.anomalies.common import (
    Tables,
)
from finance_reconciliation.generator.anomalies.models import (
    AnomalyRecord,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.accounting import (
    inject_ledger_amount_mismatch,
    inject_missing_ledger_posting,
    inject_unbalanced_journal,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.bank import (
    inject_bank_amount_mismatch,
    inject_missing_bank_receipt,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.fx import (
    inject_fx_rate_outlier,
    inject_missing_fx_rate,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.product import (
    inject_unmapped_product,
)
from finance_reconciliation.generator.anomalies.reconciliation_controls.settlement import (
    inject_settlement_total_mismatch,
)
from finance_reconciliation.generator.anomalies.state import (
    AnomalyInjectionState,
)


def inject_reconciliation_control_anomalies(
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

    inject_settlement_total_mismatch(
        tables,
        state=state,
    )

    inject_missing_bank_receipt(
        tables,
        state=state,
    )

    inject_bank_amount_mismatch(
        tables,
        state=state,
    )

    inject_missing_ledger_posting(
        tables,
        state=state,
    )

    inject_ledger_amount_mismatch(
        tables,
        state=state,
    )

    inject_unbalanced_journal(
        tables,
        state=state,
    )

    inject_missing_fx_rate(
        tables,
        state=state,
    )

    inject_fx_rate_outlier(
        tables,
        state=state,
    )

    inject_unmapped_product(
        tables,
        state=state,
    )

    return state.anomalies[
        start_index:
    ]