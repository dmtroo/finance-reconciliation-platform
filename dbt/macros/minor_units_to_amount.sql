{% macro minor_units_to_amount(column_name) %}
    (
        {{ column_name }}::numeric
        / 100
    )::numeric(18, 2)
{% endmacro %}