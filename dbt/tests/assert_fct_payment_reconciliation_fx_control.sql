select
    capture_id,
    psp_fx_rate_variance_ratio,
    is_fx_rate_outlier

from {{ ref('fct_payment_reconciliation') }}

where
    psp_fx_rate_variance_ratio is not null

    and is_fx_rate_outlier is distinct from (
        abs(psp_fx_rate_variance_ratio)
        > {{ var('reconciliation_fx_outlier_ratio') }}
    )