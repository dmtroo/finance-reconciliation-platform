with source_events as (

    select financial_event_id
    from {{ ref('int_financial_events__with_reference_fx') }}

),

settlement_mapping as (

    select financial_event_id
    from {{ ref('int_financial_events__settlement_mapping') }}

),

missing_from_mapping as (

    select financial_event_id
    from source_events

    except

    select financial_event_id
    from settlement_mapping

),

unexpected_in_mapping as (

    select financial_event_id
    from settlement_mapping

    except

    select financial_event_id
    from source_events

)

select *
from missing_from_mapping

union all

select *
from unexpected_in_mapping