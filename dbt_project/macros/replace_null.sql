{% macro replace_null(column, datatype) %}

{% if datatype == 'NUMBER' %}
COALESCE({{ column }}, 0)

{% elif datatype == 'TEXT' %}
COALESCE({{ column }}, 'UNKNOWN')

{% elif datatype == 'DATE' %}
{{ column }}

{% else %}
{{ column }}

{% endif %}

{% endmacro %}