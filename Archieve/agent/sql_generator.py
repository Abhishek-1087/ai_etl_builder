# from agent.llm import ask_llm


# def generate_dbt_sql(schema, user_request, source_table):

#     schema_text = "\n".join(
#         [f"{col} ({dtype})" for col, dtype in schema]
#     )

#     prompt = f"""
# You are a senior analytics engineer.

# SOURCE TABLE
# {source_table}

# SCHEMA
# {schema_text}

# USER REQUEST
# {user_request}

# Return ONLY valid JSON.

# Do NOT include:
# - explanations
# - markdown
# - ```json

# Format:

# {{
#  "models":[
#    {{
#      "name":"model_name",
#      "sql":"SQL"
#    }}
#  ]
# }}
# """

#     sql = ask_llm(prompt)

#     return sql



from agent.llm import ask_llm
import re


import re


def extract_sql(text):

    text = text.replace("```sql", "").replace("```", "")

    lines = text.splitlines()

    sql_lines = []
    for line in lines:
        if line.lower().startswith("this sql"):
            break
        sql_lines.append(line)

    return "\n".join(sql_lines).strip()


def generate_mart_sql(tables, request):

    prompt = f"""
You are a senior analytics engineer writing DBT models.

Available staging tables:

{tables}

Rules:

1. Use ONLY staging models
2. Use ref() syntax
3. Do not reference raw tables
4. Return only SQL
5. No explanation

Example style:

SELECT
    c.customer_id,
    oi.order_id,
    oi.product_id,
    COUNT(oi.quantity) AS total_items
FROM {{{{ ref('stg_customer') }}}} c
JOIN {{{{ ref('stg_order_detail') }}}} o
    ON c.customer_id = o.customer_id
JOIN {{{{ ref('stg_order_item') }}}} oi
    ON oi.order_id = o.order_id
GROUP BY
    c.customer_id,
    oi.product_id,
    oi.order_id

User request:
{request}
"""

    response = ask_llm(prompt)

    print("\nLLM RESPONSE:\n", response)

    sql = extract_sql(response)

    return {
        "models":[
            {
                "name":"mart_customer_revenue",
                "layer":"mart",
                "sql":sql
            }
        ]
    }