select
    business_date,
    product_id,
    currency,
    count(*) as row_count

from {{ ref('mart_finance_daily') }}

group by
    business_date,
    product_id,
    currency

having count(*) > 1