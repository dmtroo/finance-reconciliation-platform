with source_events as (

    select financial_event_id
    from {{ ref('int_financial_events__with_reference_fx') }}

),

accounting_context as (

    select financial_event_id
    from {{ ref('int_financial_events__accounting_context') }}

),

missing_from_context as (

    select financial_event_id
    from source_events

    except

    select financial_event_id
    from accounting_context

),

unexpected_in_context as (

    select financial_event_id
    from accounting_context

    except

    select financial_event_id
    from source_events

)

select *
from missing_from_context

union all

select *
from unexpected_in_context