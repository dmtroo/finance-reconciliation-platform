select
    financial_event_id,
    event_date,
    reference_fx_rate_date

from {{ ref('int_financial_events__with_reference_fx') }}

where
    reference_fx_rate_date > event_date