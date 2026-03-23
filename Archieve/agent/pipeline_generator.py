import json
import re
from agent.llm import ask_llm


def extract_json(text):

    text = text.replace("```json", "").replace("```", "")

    match = re.search(r"\{[\s\S]*\}", text)

    if not match:
        raise ValueError("No JSON found")

    try:
        return json.loads(match.group(0))
    except:
        raise ValueError("Invalid JSON from LLM")


def clean_sql(sql):
    """
    Clean SQL so dbt can run it
    """

    sql = sql.replace("\n", " ")
    sql = re.sub(r"\s+", " ", sql)

    # remove CREATE TABLE if LLM generates it
    sql = re.sub(
        r"CREATE\s+OR\s+REPLACE\s+TABLE.*?AS",
        "",
        sql,
        flags=re.IGNORECASE
    )

    return sql.strip()


def generate_pipeline(user_request):

    prompt = f"""
You are a senior analytics engineer building dbt MART models.

IMPORTANT:
Return ONLY valid JSON.
Do NOT return Python code.
Do NOT include explanations.

Staging tables already exist:

customer
order_details
order_item
product

Schema:

customer(customer_id, first_name, last_name, city, email, signup_date)
order_details(order_id, customer_id, order_date, total_amount, status)
order_item(order_item_id, order_id, product_id, quantity, unit_price)
product(product_id, product_name, category, price)

Goal:
Generate 2-3 useful MART models with business insights.

Rules:
- Use {{ ref('table') }} for joins
- NEVER use source()
- ONLY SELECT statements
- Include aggregations
- Model names must start with mart_

Example:

SELECT
    c.customer_id,
    COUNT(o.order_id) AS total_orders
FROM {{ ref('customer') }} c
LEFT JOIN {{ ref('order_details') }} o
    ON c.customer_id = o.customer_id
GROUP BY c.customer_id

Return ONLY JSON in this format:

{{
 "models":[
  {{
   "name":"mart_model_name",
   "sql":"SELECT ..."
  }}
 ]
}}
"""

    response = ask_llm(prompt)

    print("\n========== LLM RESPONSE ==========")
    print(response)
    print("==================================\n")

    json_text = extract_json(response)

    pipeline = json.loads(json_text)

    # clean SQL
    for model in pipeline["models"]:
        model["sql"] = clean_sql(model["sql"])

    return pipeline