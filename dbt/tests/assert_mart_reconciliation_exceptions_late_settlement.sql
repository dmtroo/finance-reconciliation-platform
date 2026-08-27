select
    exception_id,
    exception_status,
    severity,
    age_days

from {{ ref('mart_reconciliation_exceptions') }}

where
    exception_code = 'LATE_SETTLEMENT'

    and (
        exception_status != 'RESOLVED'
        or severity != 'WARNING'
        or age_days
            <= {{ var('reconciliation_settlement_pending_days') }}
    )