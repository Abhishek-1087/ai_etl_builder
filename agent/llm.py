import ollama

# def ask_llm(prompt):

#     response = ollama.chat(
#         model="deepseek-coder",
#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]
#     )

#     return response['message']['content']

# import ollama


import ollama
import time

MODEL = "deepseek-coder"


def ask_llm(prompt, retries=3):

    system_prompt = """You are a SQL code completion engine.
Continue the SQL code exactly where it stops.
Return ONLY raw SQL. No explanation. No markdown. No comments."""

    for attempt in range(retries):

        try:

            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                options={"temperature": 0}
            )

            return response["message"]["content"]

        except Exception as e:

            if attempt == retries - 1:
                raise e

            time.sleep(2)