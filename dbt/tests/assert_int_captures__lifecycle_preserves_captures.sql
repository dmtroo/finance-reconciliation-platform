with source_captures as (

    select
        financial_event_id as capture_id

    from {{ ref('int_financial_events__with_reference_fx') }}

    where event_type = 'CAPTURE'

),

lifecycle_captures as (

    select capture_id
    from {{ ref('int_captures__lifecycle') }}

),

missing_from_lifecycle as (

    select capture_id
    from source_captures

    except

    select capture_id
    from lifecycle_captures

),

unexpected_in_lifecycle as (

    select capture_id
    from lifecycle_captures

    except

    select capture_id
    from source_captures

)

select *
from missing_from_lifecycle

union all

select *
from unexpected_in_lifecycle