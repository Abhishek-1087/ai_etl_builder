from agent.llm import ask_llm
from agent.json_utils import extract_json


def plan_pipeline(user_request):

    prompt = f"""
You are a senior data engineer.

Your task is to design a DBT pipeline.

IMPORTANT:
Return ONLY JSON.
Do not explain anything.
Do not include markdown.
Do not include text outside JSON.

User request:
{user_request}

Return exactly this structure:

{{
 "models":[
  {{
   "name":"stg_orders",
   "description":"staging orders"
  }},
  {{
   "name":"mart_customer_revenue",
   "description":"customer revenue mart"
  }}
 ]
}}
"""

    response = ask_llm(prompt)

    print("\nLLM RESPONSE:")
    print(response)

    return extract_json(response)