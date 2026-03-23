# def generate_staging_models(schema):

#     models = []

#     for table, columns in schema.items():

#         lines = []

#         for col in columns:

#             column = col["column"]
#             dtype = col["type"]

#             lines.append(
#                 f"  {{{{ replace_null('{column}', '{dtype}') }}}} AS {column}"
#             )

#         select_clause = ",\n".join(lines)

#         sql = f"""
#         {{{{ config(materialized='view') }}}}
# SELECT
# {select_clause}
# FROM {{{{ source('raw','{table}') }}}}
# """

#         models.append({
#             "name": f"stg_{table.lower()}",
#             "layer": "staging",
#             "sql": sql
#         })

#     return models



import os


def generate_staging_models(schema):

    models = []

    staging_folder = "dbt_project/models/staging"

    os.makedirs(staging_folder, exist_ok=True)

    for table, columns in schema.items():

        model_name = f"stg_{table.lower()}"
        file_path = os.path.join(staging_folder, f"{model_name}.sql")

        # Skip if staging model already exists
        if os.path.exists(file_path):

            print(f"Skipping existing staging model: {model_name}")

            continue

        lines = []

        for col in columns:

            column = col["column"]
            dtype = col["type"]

            lines.append(
                f"  {{{{ replace_null('{column}', '{dtype}') }}}} AS {column}"
            )

        select_clause = ",\n".join(lines)

        sql = f"""
{{{{ config(materialized='view') }}}}

SELECT
{select_clause}
FROM {{{{ source('raw','{table}') }}}}
"""

        models.append({
            "name": model_name,
            "layer": "staging",
            "sql": sql
        })

    return models