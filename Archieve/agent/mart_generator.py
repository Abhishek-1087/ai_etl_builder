import re
from agent.llm import ask_llm

def clean_sql(sql):

    # remove markdown
    sql = sql.replace("```sql", "").replace("```", "")

    # remove explanation text
    sql = re.split(r"\n\s*This SQL", sql)[0]

    # fix ref syntax
    sql = sql.replace("{ref(", "{{ ref(")
    sql = sql.replace(")}", ") }}")

    # ensure staging refs
    sql = re.sub(
        r"\bstg_(\w+)",
        r"{{ ref('stg_\1') }}",
        sql
    )

    return sql.strip()



def generate_mart(insight, schema_context, joins):

    prompt = f"""
You are a senior analytics engineer.

Schema:

{schema_context}
Available joins:

{joins}

Create a DBT mart model for:

{insight}

Rules:
- Use DBT ref() syntax for tables
- Use {{{{ ref('stg_table') }}}}
- Return SQL only
- Do NOT explain anything
- Do NOT add text before or after SQL
- Always alias tables
- Use aliases in SELECT, JOIN, GROUP BY
"""

    response = ask_llm(prompt)

    sql = clean_sql(response)

    return {
        "name": f"mart_{insight}",
        "layer": "mart",
        "sql": sql
    }