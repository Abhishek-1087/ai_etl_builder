from agent.schema_reader import read_schema
from agent.staging_model_generator import generate_staging_models
from agent.staging_view_reader import read_staging_views
from agent.insight_planner import plan_insights
from agent.mart_generator import generate_mart
from agent.dbt_model_creator import create_models
from agent.schema_context import build_schema_context
from agent.join_detector import detect_joins
from agent.schema_drift_detector import detect_drift, print_drift_report
from agent.data_profiler import run_data_profiling, score_trust, print_profile_summary
from agent.self_healing_runner import run_dbt_with_healing
from agent.dashboard_reporter import generate_and_save
from dotenv import load_dotenv
import os
import re

load_dotenv()

connection = {
    "user":      os.getenv("SNOWFLAKE_USER"),
    "password":  os.getenv("SNOWFLAKE_PASSWORD"),
    "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database":  os.getenv("SNOWFLAKE_DATABASE"),
    "schema":    os.getenv("SNOWFLAKE_SCHEMA"),
    "role":      os.getenv("SNOWFLAKE_ROLE"),
}


def repair_llm_sql(sql):
    """Fix common LLM SQL generation mistakes before writing to dbt."""

    sql = re.sub(
        r"\{\{\s*ref\('\{\{\s*ref\('([^']+)'\)\s*\}\}'\)\s*\}\}",
        r"{{ ref('\1') }}",
        sql
    )
    sql = re.sub(r"\}\}'\)\s*\}\}", "}}", sql)
    sql = re.sub(r"\}\}'\)", "}}", sql)
    sql = re.sub(r"\{\{\s*\{\{\s*", "{{ ", sql)
    sql = re.sub(r"\s*\}\}\s*\}\}", " }}", sql)

    tables = list(set(re.findall(r"stg_[a-zA-Z0-9_]+", sql)))
    alias_map = {}
    for t in tables:
        parts = t.split("_")[1:]
        alias = "".join([p[0] for p in parts if p])
        alias_map[t] = alias

    for table, alias in alias_map.items():
        sql = re.sub(
            r"FROM\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}",
            "FROM {{ ref('" + table + "') }} " + alias, sql
        )
        sql = re.sub(
            r"JOIN\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}\s+\{\{\s*ref\('" + table + r"'\)\s*\}\}",
            "JOIN {{ ref('" + table + "') }} " + alias, sql
        )

    for table, alias in alias_map.items():
        pattern = r"\{\{\s*ref\('" + table + r"'\)\s*\}\}\."
        sql = re.sub(pattern, alias + ".", sql)

    return sql


def run_pipeline():

    print("=" * 50)
    print("  AI-NATIVE AGENTIC ETL PIPELINE STARTED")
    print("=" * 50)

    # STEP 1 — Read Snowflake schema
    print("\n[1/9] Reading schema from Snowflake...")
    schema = read_schema(connection)
    print(f"\nTables discovered: {len(schema)}")
    for table, cols in schema.items():
        print(f"  {table} ({len(cols)} columns)")

    # STEP 2 — Schema drift detection
    print("\n[2/9] Checking for schema drift...")
    drift = detect_drift(schema)
    print_drift_report(drift)

    # STEP 3 — Data profiling & trust scoring
    print("\n[3/9] Profiling data quality...")
    raw_profiles = run_data_profiling(connection, schema)
    scored_profiles = score_trust(raw_profiles)
    print_profile_summary(scored_profiles)

    # STEP 4 — Detect join relationships
    print("\n[4/9] Detecting join relationships...")
    joins = detect_joins(schema)
    for j in joins:
        print(f"  {j}")
    schema_context = build_schema_context(schema)

    # STEP 5 — Generate staging models (skip existing)
    print("\n[5/9] Generating staging models...")
    staging_models = generate_staging_models(schema)
    print(f"Generated {len(staging_models)} new staging models")

    # STEP 6 — Read staging views from Snowflake
    print("\n[6/9] Reading staging views from Snowflake...")
    views = read_staging_views(connection)
    print(f"Found {len(views)} staging views")

    # STEP 7 — Plan analytics insights
    print("\n[7/9] Planning analytics insights...")
    insights = plan_insights(schema_context)
    insights = [i for i in insights if i]
    print(f"\nInsights planned: {len(insights)}")
    for i in insights:
        print(f"  - {i}")

    # Clean old mart models
    mart_path = "dbt_project/models/mart"
    os.makedirs(mart_path, exist_ok=True)
    for f in os.listdir(mart_path):
        if f.startswith("mart_"):
            os.remove(os.path.join(mart_path, f))

    # STEP 8 — Generate mart models
    print("\n[8/9] Generating mart models...")
    mart_models = []
    for insight in insights:
        model = generate_mart(insight, schema_context, joins)
        model["sql"] = repair_llm_sql(model["sql"])
        print(model)
        mart_models.append(model)
        print(f"  Generated: {model['name']}")

    all_models = staging_models + mart_models
    create_models(all_models)

    # STEP 9 — Run dbt with self-healing
    print("\n[9/9] Running dbt (self-healing enabled)...")
    dbt_success, run_log = run_dbt_with_healing()

    # FINAL — Generate delivery health dashboard
    print("\nGenerating delivery health dashboard...")
    report = generate_and_save(
        schema=schema,
        drift=drift,
        scored_profiles=scored_profiles,
        dbt_success=dbt_success,
        run_log=run_log,
        mart_models=mart_models
    )

    print("\n" + "=" * 50)
    if dbt_success:
        print("  PIPELINE COMPLETED SUCCESSFULLY")
        print(f"  Overall data trust score: {report['overall_trust_score']}/100")
    else:
        print("  PIPELINE FAILED - check pipeline_dashboard.html for details")
    print("=" * 50)
    print(f"\nDashboard: pipeline_dashboard.html")
    print(f"JSON report: pipeline_report.json\n")


if __name__ == "__main__":
    run_pipeline()
