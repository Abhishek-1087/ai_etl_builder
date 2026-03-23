import re
from agent.llm import ask_llm


def plan_insights(schema_context):

    prompt = f"""
You are a senior analytics engineer.

Schema:

{schema_context}

Generate useful business analytics insights.

Return ONLY insight names
So please check the schema and generate insights name only
"""

    response = ask_llm(prompt)

    insights = []

    for line in response.split("\n"):

        line = line.strip()

        # remove numbering
        line = re.sub(r"^\d+\.\s*", "", line)

        # normalize
        line = line.lower().replace(" ", "_")

        # keep only valid characters
        line = re.sub(r"[^a-z0-9_]", "", line)

        if line:
            insights.append(line)

    return insights