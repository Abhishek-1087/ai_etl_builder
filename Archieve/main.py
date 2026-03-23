# from agent.schema_reader import read_schema
# from agent.staging_model_generator import generate_staging_models
# from agent.sql_generator import generate_mart_sql
# from agent.dbt_model_creator import create_models
# from agent.dbt_runner import run_dbt
# from agent.staging_view_reader import read_staging_views
# from agent.insight_planner import plan_insights
# from agent.mart_generator import generate_mart


# connection = {
#     "user": "Abhishek",
#     "password": "Sonu@1234567890",
#     "account": "SREVWOM-EUB49120",
#     "warehouse": "COMPUTE_WH",
#     "database": "AI_ETL_DB",
#     "schema": "RAW",
#     "role": "ACCOUNTADMIN"
# }


# def run_pipeline(request):

#     print("Reading schema...")

#     schema = read_schema(connection)
#     print("\nTables discovered from INFORMATION_SCHEMA:\n")

#     for table, cols in schema.items():

#         print(f"\n{table}")

#         for col in cols:
#             print(f"   {col['column']} ({col['type']})")

#     print("Generating staging models...")

#     staging_models = generate_staging_models(schema)

#     print(f"\nGenerated {len(staging_models)} staging models")
#     views = read_staging_views(connection)

#     insights = plan_insights(views)
#     mart_models = []

#     for insight in insights:
#         mart_models.append(generate_mart(insight))

#     mart_models = generate_mart_sql(list(schema.keys()), request)

#     all_models = staging_models + mart_models["models"]

#     print("Creating DBT models...")

#     create_models(all_models)

#     print("Running DBT...")

#     success = run_dbt()

#     if success:
#         print("\nPipeline completed successfully 🚀")
#     else:
#         print("\nPipeline failed ❌")


# if __name__ == "__main__":

#     run_pipeline("Build mart for customer revenue")




from agent.schema_reader import read_schema
from agent.staging_model_generator import generate_staging_models
from agent.staging_view_reader import read_staging_views
from agent.insight_planner import plan_insights
from agent.mart_generator import generate_mart
from agent.dbt_model_creator import create_models
from agent.dbt_runner import run_dbt
from agent.schema_context import build_schema_context
from agent.join_detector import detect_joins
from dotenv import load_dotenv
import os
import re 
load_dotenv()

connection = {
"user": os.getenv("SNOWFLAKE_USER"),
"password": os.getenv("SNOWFLAKE_PASSWORD"),
"account": os.getenv("SNOWFLAKE_ACCOUNT"),
"warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
"database": os.getenv("SNOWFLAKE_DATABASE"),
"schema": os.getenv("SNOWFLAKE_SCHEMA"),
"role": os.getenv("SNOWFLAKE_ROLE")
}


import re

import re

def repair_llm_sql(sql):

    # 1️⃣ Fix nested ref like {{ ref('{{ ref('stg_customer') }}') }}
    sql = re.sub(
        r"\{\{\s*ref\('\{\{\s*ref\('([^']+)'\)\s*\}\}'\)\s*\}\}",
        r"{{ ref('\1') }}",
        sql
    )

    # 2️⃣ Fix trailing brackets {{ ref('table') }}') }}
    sql = re.sub(r"\}\}'\)\s*\}\}", "}}", sql)
    sql = re.sub(r"\}\}'\)", "}}", sql)

    # 3️⃣ Remove double braces {{ {{ ref() }} }}
    sql = re.sub(r"\{\{\s*\{\{\s*", "{{ ", sql)
    sql = re.sub(r"\s*\}\}\s*\}\}", " }}", sql)

    # 4️⃣ Detect staging tables
    tables = list(set(re.findall(r"stg_[a-zA-Z0-9_]+", sql)))

    alias_map = {}

    for t in tables:
        parts = t.split("_")[1:]
        alias = "".join([p[0] for p in parts])
        alias_map[t] = alias

    # 5️⃣ Fix FROM and JOIN aliases
    for table, alias in alias_map.items():

        # FROM clause
        sql = re.sub(
            r"FROM\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}",
            "FROM {{ ref('" + table + "') }} " + alias,
            sql
        )

        # JOIN clause
        sql = re.sub(
            r"JOIN\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}",
            "JOIN {{ ref('" + table + "') }} " + alias,
            sql
        )

    # 6️⃣ Replace column references
    for table, alias in alias_map.items():

        pattern = r"\{\{\s*ref\('" + table + r"'\)\s*\}\}\."
        sql = re.sub(pattern, alias + ".", sql)

    return sql


def run_pipeline(request):

    print("AI ETL PIPELINE STARTED")

    # STEP 1 — Read Snowflake schema
    print("Reading schema...")

    schema = read_schema(connection)

    print("\nDetected joins:\n")
    
    joins = detect_joins(schema)
    for j in joins:
        print(j)
        
    schema_context = build_schema_context(schema)

    print("\nTables discovered from INFORMATION_SCHEMA:\n")

    for table, cols in schema.items():

        print(f"\n{table}")

        for col in cols:
            print(f"   {col['column']} ({col['type']})")

    # STEP 2 — Generate staging models
    print("\nGenerating staging models...")

    staging_models = generate_staging_models(schema)

    print(f"\nGenerated {len(staging_models)} staging models")

    # STEP 3 — Detect staging views
    print("\nReading staging views from Snowflake...")

    views = read_staging_views(connection)

    print("\nDetected staging views:")

    for v in views:
        print(v)

    # STEP 4 — Ask AI for insights
    print("\nPlanning analytics insights...")

    insights = plan_insights(schema_context)
    insights = insights[1:-1]

    print("\nInsights selected:")

    for i in insights:
        print(i)

    # STEP 5 — Clean old mart models
    mart_path = "dbt_project/models/mart"

    os.makedirs(mart_path, exist_ok=True)

    print("\nCleaning old mart models...")

    for f in os.listdir(mart_path):
        if f.startswith("mart_"):
            os.remove(os.path.join(mart_path, f))
            print(f"Deleted old model: {f}")


    # STEP 6 — Generate mart models
    print("\nGenerating mart models...")

    mart_models = []

    for insight in insights:

        model = generate_mart(insight, schema_context, joins)
        
        print(model)
        # normalize LLM SQL
        model["sql"] = repair_llm_sql(model["sql"])

        mart_models.append(model)

        print(f"Generated mart model: {model['name']}")
    # STEP 7 — Combine models
    all_models = staging_models + mart_models

    # STEP 8 — Create DBT models
    print("\nCreating DBT models...")

    create_models(all_models)

    # STEP 9 — Run DBT
    print("\nRunning DBT...")

    success = run_dbt()

    # FINAL STATUS
    if success:

        print("\n===================================")
        print("PIPELINE COMPLETED SUCCESSFULLY 🚀")
        print("===================================\n")

    else:

        print("\n===================================")
        print("PIPELINE FAILED ❌")
        print("===================================\n")

if __name__ == "__main__":

    run_pipeline("Build mart for customer revenue")
