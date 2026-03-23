# from agent.llm import ask_llm


# def generate_insight_models(schema):

#     schema_text = ""

#     for table, columns in schema.items():

#         schema_text += f"\nTable: {table}\n"

#         for col, dtype in columns:
#             schema_text += f"- {col} ({dtype})\n"


#     prompt = f"""
# You are a senior analytics engineer.

# The following tables exist in Snowflake RAW schema:

# {schema_text}

# Generate dbt SQL models to create business insights.

# Create models for:

# 1. Daily revenue
# 2. Customer lifetime value
# 3. Top products
# 4. Revenue by category
# 5. Order status distribution

# Return response in JSON:

# {{
#  "fct_daily_revenue": "SQL HERE",
#  "fct_customer_ltv": "SQL HERE",
#  "fct_top_products": "SQL HERE",
#  "fct_category_revenue": "SQL HERE",
#  "fct_order_status": "SQL HERE"
# }}

# Use dbt syntax:

# {{{{ source('raw','TABLE_NAME') }}}}
# """

#     response = ask_llm(prompt)

#     return response


from agent.llm import ask_llm


def generate_insights(data):

    prompt = f"""
You are a data analyst.

Analyze this dataset.

DATA
{data}

Provide business insights.
"""

    return ask_llm(prompt)