select
    exception_id,
    exception_status,
    severity,
    age_days

from {{ ref('mart_reconciliation_exceptions') }}

where
    exception_code = 'MISSING_BANK_RECEIPT'

    and (
        (
            age_days
                <= {{ var('reconciliation_bank_pending_days') }}

            and (
                exception_status != 'PENDING'
                or severity != 'INFO'
            )
        )

        or

        (
            age_days
                > {{ var('reconciliation_bank_pending_days') }}

            and (
                exception_status != 'OPEN_BREAK'
                or severity != 'CRITICAL'
            )
        )
    )