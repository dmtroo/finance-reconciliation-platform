select
    rate_date,
    currency,
    units_per_eur,
    eur_per_unit,
    is_derived_rate

from {{ ref('stg_ecb__fx_rates') }}

where
    units_per_eur <= 0

    or eur_per_unit <= 0

    or (
        currency = 'EUR'
        and (
            units_per_eur != 1
            or eur_per_unit != 1
            or is_derived_rate is not true
        )
    )

    or (
        currency != 'EUR'
        and (
            is_derived_rate is not false
            or abs(
                units_per_eur * eur_per_unit - 1
            ) > 0.000001
        )
    )