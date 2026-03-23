from agent.llm import ask_llm


def fix_sql(error, sql):

    prompt = f"""
You are a senior analytics engineer.

The following DBT SQL failed.

DBT ERROR:
{error}

SQL:
{sql}

Fix the SQL.

Return ONLY corrected SQL.
No explanation.
"""

    fixed_sql = ask_llm(prompt)

    return fixed_sql