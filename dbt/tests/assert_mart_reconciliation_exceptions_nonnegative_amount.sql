select
    exception_id,
    exception_code,
    exception_amount_eur

from {{ ref('mart_reconciliation_exceptions') }}

where exception_amount_eur < 0