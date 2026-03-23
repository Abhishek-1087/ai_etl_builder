"""
AI-Native Agentic ETL Builder with Self-Healing Pipelines
----------------------------------------------------------
Usage:
    python main.py              # full run, auto-approve all models
    python main.py --review     # run to mart generation, save for UI review
    python main.py --execute    # run dbt with UI-approved models only

The --review / --execute split enables the human-in-the-loop workflow
available in the Streamlit UI (ui/app.py).
"""

import os
import sys
import json
import argparse
from dotenv import load_dotenv

from agent.schema_reader import read_schema
from agent.staging_model_generator import generate_staging_models
from agent.staging_view_reader import read_staging_views
from agent.insight_planner import plan_insights
from agent.dbt_model_creator import create_models
from agent.schema_context import build_schema_context
from agent.join_detector import detect_joins
from agent.schema_drift_detector import detect_drift, print_drift_report
from agent.data_profiler import run_data_profiling, score_trust, print_profile_summary
from agent.self_healing_runner import run_dbt_with_healing
from agent.dashboard_reporter import generate_and_save
from registry.model_registry import (
    init_db, save_run, get_stats, detect_domain
)
from registry.composition_agent import (
    compose_marts, save_successful_models, get_composition_stats
)

load_dotenv()

# ── Connection config ─────────────────────────────────────────────────────────

connection = {
    "user":      os.getenv("SNOWFLAKE_USER"),
    "password":  os.getenv("SNOWFLAKE_PASSWORD"),
    "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE"),
    "database":  os.getenv("SNOWFLAKE_DATABASE"),
    "schema":    os.getenv("SNOWFLAKE_SCHEMA"),
    "role":      os.getenv("SNOWFLAKE_ROLE"),
}

PENDING_FILE  = "pending_review.json"
APPROVAL_FILE = "approvals.json"


# ── Banner ────────────────────────────────────────────────────────────────────

def print_banner():
    print("=" * 55)
    print("  AI-NATIVE AGENTIC ETL BUILDER")
    print("  with Self-Healing Pipelines + Model Registry")
    print("=" * 55)
    try:
        stats = get_stats()
        if stats["total_models"] > 0:
            print(
                f"  Registry: {stats['total_models']} models | "
                f"Avg quality: {stats['avg_quality']}/100"
            )
    except Exception:
        pass
    print("=" * 55 + "\n")


# ── Pipeline phases ───────────────────────────────────────────────────────────

def phase_read_schema():
    print("[1/9] Reading schema from Snowflake...")
    schema = read_schema(connection)
    print(f"\n  Tables discovered: {len(schema)}")
    for table, cols in schema.items():
        print(f"    {table} ({len(cols)} columns)")
    return schema


def phase_drift(schema):
    print("\n[2/9] Checking for schema drift...")
    drift = detect_drift(schema)
    print_drift_report(drift)
    return drift


def phase_profile(schema):
    print("\n[3/9] Profiling data quality...")
    raw_profiles    = run_data_profiling(connection, schema)
    scored_profiles = score_trust(raw_profiles)
    print_profile_summary(scored_profiles)
    return scored_profiles


def phase_joins(schema):
    print("\n[4/9] Detecting join relationships...")
    joins = detect_joins(schema)
    # Deduplicate joins
    seen = set()
    unique_joins = []
    for j in joins:
        parts = tuple(sorted(j.split(" = ")))
        if parts not in seen:
            seen.add(parts)
            unique_joins.append(j)
    for j in unique_joins:
        print(f"  {j}")
    return unique_joins


def phase_staging(schema):
    print("\n[5/9] Generating staging models...")
    staging_models = generate_staging_models(schema)
    print(f"  Generated {len(staging_models)} new staging models")
    return staging_models


def phase_staging_views():
    print("\n[6/9] Reading staging views from Snowflake...")
    views = read_staging_views(connection)
    print(f"  Found {len(views)} staging views")
    return views


def phase_insights(schema_context):
    print("\n[7/9] Planning analytics insights...")
    insights = plan_insights(schema_context)
    insights = [i for i in insights if i]
    print(f"\n  Insights planned: {len(insights)}")
    for i in insights:
        print(f"    - {i}")
    return insights


def phase_compose(insights, schema, schema_context, joins):
    print("\n[8/9] Composing mart models (registry-first)...")

    # Clean old mart models
    mart_path = "dbt_project/models/mart"
    os.makedirs(mart_path, exist_ok=True)
    for f in os.listdir(mart_path):
        if f.startswith("mart_"):
            os.remove(os.path.join(mart_path, f))

    mart_models = compose_marts(insights, schema, schema_context, joins)
    comp_stats  = get_composition_stats(mart_models)

    print(f"\n  Hit rate: {comp_stats['hit_rate_pct']}%")
    print(f"  From registry: {comp_stats['from_registry']}")
    print(f"  Adapted:       {comp_stats['adapted']}")
    print(f"  Generated:     {comp_stats['generated']}")

    return mart_models, comp_stats


def phase_dbt():
    print("\n[9/9] Running dbt (self-healing enabled)...")
    return run_dbt_with_healing()


# ── Main pipeline modes ───────────────────────────────────────────────────────

def run_full_pipeline():
    """Standard run — auto-approves all models."""
    print_banner()
    init_db()

    schema         = phase_read_schema()
    drift          = phase_drift(schema)
    scored_profiles = phase_profile(schema)
    joins          = phase_joins(schema)
    schema_context = build_schema_context(schema)
    staging_models = phase_staging(schema)
    _              = phase_staging_views()
    insights       = phase_insights(schema_context)
    mart_models, comp_stats = phase_compose(
        insights, schema, schema_context, joins
    )

    # Write all models
    all_models = staging_models + mart_models
    create_models(all_models)

    # Run dbt
    dbt_success, run_log = phase_dbt()

    # Save to registry on success
    if dbt_success:
        print("\n  Saving successful models to registry...")
        save_successful_models(mart_models, schema)

    # Log run
    trust_score = (
        sum(p["trust_score"] for p in scored_profiles) / len(scored_profiles)
        if scored_profiles else 0
    )
    save_run(
        schema         = schema,
        models_built   = len(mart_models),
        models_healed  = 0,
        trust_score    = trust_score,
        dbt_success    = dbt_success,
        drift_detected = drift.get("has_drift", False)
    )

    # Dashboard
    print("\n  Generating delivery health dashboard...")
    report = generate_and_save(
        schema          = schema,
        drift           = drift,
        scored_profiles = scored_profiles,
        dbt_success     = dbt_success,
        run_log         = run_log,
        mart_models     = mart_models
    )

    _print_final_status(dbt_success, report, comp_stats)


def run_review_mode():
    """
    Run pipeline up to mart generation.
    Saves proposed models to pending_review.json for UI approval.
    Does NOT run dbt.
    """
    print_banner()
    print("MODE: Review — pipeline will stop before dbt execution.\n")
    print("Open the UI to review and approve models:")
    print("  streamlit run ui/app.py\n")
    init_db()

    schema         = phase_read_schema()
    drift          = phase_drift(schema)
    scored_profiles = phase_profile(schema)
    joins          = phase_joins(schema)
    schema_context = build_schema_context(schema)
    staging_models = phase_staging(schema)
    _              = phase_staging_views()
    insights       = phase_insights(schema_context)
    mart_models, comp_stats = phase_compose(
        insights, schema, schema_context, joins
    )

    # Save proposed models for UI review
    pending = []
    for m in mart_models:
        pending.append({
            "name":           m["name"],
            "sql":            m["sql"],
            "source":         m.get("source", "generated"),
            "confidence":     m.get("confidence", 0),
            "registry_match": m.get("registry_match"),
        })

    with open(PENDING_FILE, "w") as f:
        json.dump(pending, f, indent=2)

    print(f"\n  {len(pending)} models saved to {PENDING_FILE}")
    print("  Open the UI, review, then run:")
    print("  python main.py --execute")

    # Also write staging models so they're ready
    create_models(staging_models)


def run_execute_mode():
    """
    Load UI-approved models and run dbt with only approved models.
    Must be run after --review mode and UI approval.
    """
    print_banner()
    print("MODE: Execute — running dbt with approved models only.\n")

    if not os.path.exists(PENDING_FILE):
        print("Error: No pending models found. Run --review first.")
        sys.exit(1)

    if not os.path.exists(APPROVAL_FILE):
        print("No approvals file found — approving all models by default.")
        approvals = {}
    else:
        with open(APPROVAL_FILE) as f:
            approvals = json.load(f)

    with open(PENDING_FILE) as f:
        pending = json.load(f)

    # Filter to approved models
    mart_models = []
    for model in pending:
        name     = model["name"]
        approved = approvals.get(name, True)  # default approve
        if approved:
            mart_models.append(model)
            print(f"  ✅ {name}")
        else:
            print(f"  ❌ {name} (rejected)")

    if not mart_models:
        print("\nNo models approved. Pipeline aborted.")
        sys.exit(0)

    # Write approved models to dbt
    mart_path = "dbt_project/models/mart"
    os.makedirs(mart_path, exist_ok=True)
    for f in os.listdir(mart_path):
        if f.startswith("mart_"):
            os.remove(os.path.join(mart_path, f))

    create_models(mart_models)
    print(f"\n  {len(mart_models)} models written to dbt_project/models/mart/")

    # Run dbt
    dbt_success, run_log = phase_dbt()

    # Save successful models to registry
    if dbt_success:
        print("\n  Saving successful models to registry...")

        # Reconstruct schema for registry (load from snapshot)
        try:
            schema = read_schema(connection)
            save_successful_models(mart_models, schema)
        except Exception as e:
            print(f"  Could not save to registry: {e}")

    # Cleanup
    for f in [PENDING_FILE, APPROVAL_FILE]:
        if os.path.exists(f):
            os.remove(f)

    print("\n" + "=" * 55)
    status = "COMPLETED SUCCESSFULLY" if dbt_success else "FAILED"
    print(f"  {status}")
    print("=" * 55 + "\n")


def _print_final_status(dbt_success, report, comp_stats):
    print("\n" + "=" * 55)
    if dbt_success:
        print("  PIPELINE COMPLETED SUCCESSFULLY")
        print(f"  Trust score:   {report['overall_trust_score']}/100")
        print(f"  Registry hits: {comp_stats['hit_rate_pct']}%")
        print(f"  Models built:  {comp_stats['total']}")
    else:
        print("  PIPELINE FAILED — check pipeline_dashboard.html")
    print("=" * 55)
    print(f"\n  Dashboard:   pipeline_dashboard.html")
    print(f"  JSON report: pipeline_report.json")
    print(f"  UI:          streamlit run ui/app.py\n")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI ETL Pipeline")
    parser.add_argument(
        "--review",
        action="store_true",
        help="Run pipeline to mart generation, save for UI review"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run dbt with UI-approved models from --review run"
    )
    args = parser.parse_args()

    if args.review:
        run_review_mode()
    elif args.execute:
        run_execute_mode()
    else:
        run_full_pipeline()
