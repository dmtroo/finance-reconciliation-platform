with source_captures as (

    select capture_id
    from {{ ref('int_captures__lifecycle') }}

),

reconciliation_fact as (

    select capture_id
    from {{ ref('fct_payment_reconciliation') }}

),

missing_from_fact as (

    select capture_id
    from source_captures

    except

    select capture_id
    from reconciliation_fact

),

unexpected_in_fact as (

    select capture_id
    from reconciliation_fact

    except

    select capture_id
    from source_captures

)

select *
from missing_from_fact

union all

select *
from unexpected_in_fact