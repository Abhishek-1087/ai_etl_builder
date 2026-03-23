"""
AI ETL Platform — Review UI
----------------------------
Run with: streamlit run ui/app.py

Pages:
  1. Pipeline Runner  — trigger runs, review proposed models before dbt executes
  2. Model Registry   — browse all stored models, search, view SQL
  3. Run History      — past pipeline runs with stats
  4. Settings         — LLM backend, Snowflake connection config
"""

import streamlit as st
import sys
import os
import json
import sqlite3
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from registry.model_registry import (
    get_all_models, get_run_history, get_stats,
    init_db, update_quality_score
)
from agent.llm import get_backend_info

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI ETL Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main { background-color: #0f172a; }
    .stApp { background-color: #0f172a; color: #e2e8f0; }

    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #334155;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #00A9A5;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .model-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid #00A9A5;
    }
    .model-card-registry {
        border-left-color: #22c55e;
    }
    .model-card-generated {
        border-left-color: #f59e0b;
    }
    .model-card-adapted {
        border-left-color: #3b82f6;
    }

    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-registry  { background: #14532d; color: #86efac; }
    .badge-generated { background: #451a03; color: #fcd34d; }
    .badge-adapted   { background: #1e3a5f; color: #93c5fd; }

    .status-success { color: #22c55e; font-weight: 700; }
    .status-failed  { color: #ef4444; font-weight: 700; }

    div[data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    .stSelectbox label, .stTextInput label { color: #94a3b8; }
    .stButton button {
        background-color: #00A9A5;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton button:hover { background-color: #008f8b; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚡ AI ETL Platform")
    st.markdown("---")

    page = st.radio(
        "Navigate",
        ["🚀 Pipeline Runner", "📦 Model Registry",
         "📊 Run History", "⚙️ Settings"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # LLM backend indicator
    try:
        llm_info = get_backend_info()
        colour = "#22c55e" if llm_info["type"] == "cloud_free" else "#f59e0b"
        st.markdown(
            f"**LLM:** <span style='color:{colour}'>{llm_info['backend'].upper()}</span> "
            f"— {llm_info['model']}",
            unsafe_allow_html=True
        )
    except Exception:
        st.markdown("**LLM:** Ollama (local)")

    # Quick stats
    try:
        stats = get_stats()
        st.markdown("---")
        st.markdown(f"**Registry:** {stats['total_models']} models")
        st.markdown(f"**Runs:** {stats['total_runs']} total")
        st.markdown(f"**Avg quality:** {stats['avg_quality']}/100")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — PIPELINE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

if "🚀 Pipeline Runner" in page:

    st.title("🚀 Pipeline Runner")
    st.markdown("Run the AI ETL pipeline with human-in-the-loop review before dbt executes.")

    # ── Connection status ──────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        snowflake_ok = bool(os.getenv("SNOWFLAKE_USER"))
        status = "✅ Connected" if snowflake_ok else "❌ Not configured"
        st.metric("Snowflake", status)

    with col2:
        llm_info = get_backend_info()
        st.metric("LLM", f"{llm_info['backend'].upper()} / {llm_info['model']}")

    with col3:
        try:
            stats = get_stats()
            st.metric("Registry models", stats["total_models"])
        except Exception:
            st.metric("Registry models", "0")

    with col4:
        st.metric("dbt", "✅ Ready")

    st.markdown("---")

    # ── Pipeline stages ────────────────────────────────────────────────────────
    st.subheader("Pipeline Stages")

    stages = [
        ("1", "Read Schema",        "Connect to Snowflake and discover all tables"),
        ("2", "Drift Detection",    "Compare against previous schema snapshot"),
        ("3", "Data Profiling",     "Score each table for data quality"),
        ("4", "Detect Joins",       "Find FK relationships between tables"),
        ("5", "Generate Staging",   "Auto-create stg_* dbt views (idempotent)"),
        ("6", "Plan Insights",      "LLM proposes analytics mart names"),
        ("7", "Compose Marts",      "Registry-first, LLM only for gaps"),
        ("8", "Review & Approve",   "You review proposed SQL before it runs ← YOU ARE HERE"),
        ("9", "Run dbt",            "Execute with self-healing (3 retries)"),
        ("10", "Save to Registry",  "Successful models stored for future reuse"),
    ]

    for num, name, desc in stages:
        highlight = "background: #1a3a2a;" if num == "8" else "background: #1e293b;"
        border    = "border-left: 4px solid #22c55e;" if num == "8" else "border-left: 4px solid #334155;"
        st.markdown(
            f"""<div style='{highlight} {border} border-radius:8px; padding:10px 16px;
                           margin-bottom:6px; display:flex; align-items:center; gap:12px;'>
                <span style='background:#334155; border-radius:50%; width:28px; height:28px;
                             display:inline-flex; align-items:center; justify-content:center;
                             font-size:12px; font-weight:700; color:#00A9A5;'>{num}</span>
                <div>
                  <strong style='color:#e2e8f0'>{name}</strong>
                  <span style='color:#64748b; font-size:0.85rem; margin-left:8px'>{desc}</span>
                </div>
            </div>""",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ── Review panel ───────────────────────────────────────────────────────────
    st.subheader("📋 Proposed Models — Review & Approve")
    st.markdown(
        "After running the pipeline, proposed dbt models appear here. "
        "Approve each one before dbt executes. Rejected models are skipped."
    )

    # Check if there are pending models in session state
    if "pending_models" not in st.session_state:
        st.session_state.pending_models = []
    if "approved_models" not in st.session_state:
        st.session_state.approved_models = {}

    # Simulate loading proposed models (in real use, pipeline writes these)
    pending_file = os.path.join(
        os.path.dirname(__file__), "..", "pending_review.json"
    )

    if os.path.exists(pending_file):
        with open(pending_file) as f:
            st.session_state.pending_models = json.load(f)

    if st.session_state.pending_models:
        models = st.session_state.pending_models

        # Summary row
        c1, c2, c3 = st.columns(3)
        c1.metric("Models proposed", len(models))
        c2.metric(
            "From registry",
            sum(1 for m in models if m.get("source") in ("registry", "adapted"))
        )
        c3.metric(
            "LLM generated",
            sum(1 for m in models if m.get("source") == "generated")
        )

        st.markdown("---")

        # Approve all / reject all buttons
        col_a, col_r, _ = st.columns([1, 1, 4])
        if col_a.button("✅ Approve All"):
            for m in models:
                st.session_state.approved_models[m["name"]] = True
        if col_r.button("❌ Reject All"):
            for m in models:
                st.session_state.approved_models[m["name"]] = False

        st.markdown("")

        # Individual model cards
        for model in models:
            name       = model["name"]
            source     = model.get("source", "generated")
            confidence = model.get("confidence", 0)
            sql        = model.get("sql", "")

            badge_class = {
                "registry":  "badge-registry",
                "adapted":   "badge-adapted",
                "generated": "badge-generated"
            }.get(source, "badge-generated")

            source_label = {
                "registry":  "✓ Registry",
                "adapted":   "~ Adapted",
                "generated": "+ Generated"
            }.get(source, "+ Generated")

            conf_color = "#22c55e" if confidence >= 0.8 else (
                "#f59e0b" if confidence >= 0.5 else "#ef4444"
            )

            with st.expander(f"📄 {name}  [{source_label}]", expanded=False):
                col_info, col_action = st.columns([3, 1])

                with col_info:
                    if source != "generated":
                        st.markdown(
                            f"**Source:** {model.get('registry_match', 'registry')}  "
                            f"**Confidence:** <span style='color:{conf_color}'>{confidence:.0%}</span>",
                            unsafe_allow_html=True
                        )
                    st.code(sql, language="sql")

                with col_action:
                    current = st.session_state.approved_models.get(name, True)
                    approved = st.checkbox(
                        "Approve",
                        value=current,
                        key=f"approve_{name}"
                    )
                    st.session_state.approved_models[name] = approved

                    if source in ("registry", "adapted"):
                        quality = st.slider(
                            "Quality",
                            0, 100, 100,
                            key=f"quality_{name}"
                        )
                        if st.button("Update score", key=f"score_{name}"):
                            update_quality_score(name, quality)
                            st.success("Score updated")

        # Execute button
        st.markdown("---")
        approved_count = sum(
            1 for v in st.session_state.approved_models.values() if v
        )
        st.markdown(f"**{approved_count} of {len(models)} models approved**")

        if st.button(f"▶ Run dbt with {approved_count} approved models", type="primary"):
            # Write approval decisions to a file for main.py to read
            approval_file = os.path.join(
                os.path.dirname(__file__), "..", "approvals.json"
            )
            with open(approval_file, "w") as f:
                json.dump(st.session_state.approved_models, f)
            st.success(
                f"Approvals saved. Run `python main.py --execute` to run dbt "
                f"with approved models."
            )

    else:
        st.info(
            "No pending models. Run the pipeline first:\n\n"
            "```bash\npython main.py --review\n```\n\n"
            "This runs all steps up to mart generation and saves proposed "
            "models here for your review."
        )

        # Quick run trigger
        if st.button("🚀 Run pipeline (auto-approve all)", type="primary"):
            st.info(
                "Run `python main.py` in your terminal to start the pipeline."
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — MODEL REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

elif "📦 Model Registry" in page:

    st.title("📦 Model Registry")
    st.markdown("Browse all stored dbt models. Every successful run adds models here.")

    # ── Stats ──────────────────────────────────────────────────────────────────
    try:
        stats = get_stats()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total models",   stats["total_models"])
        c2.metric("Total runs",     stats["total_runs"])
        c3.metric("Avg quality",    f"{stats['avg_quality']}/100")
        c4.metric("Successful runs", stats["success_runs"])

        # Domain breakdown
        if stats["by_domain"]:
            st.markdown("---")
            st.subheader("Models by domain")
            cols = st.columns(len(stats["by_domain"]))
            for i, (domain, count) in enumerate(stats["by_domain"].items()):
                cols[i].metric(domain.title(), count)

    except Exception as e:
        st.warning(f"Registry not initialised yet. Run the pipeline first. ({e})")

    st.markdown("---")

    # ── Filters ────────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])

    with col_f1:
        domain_filter = st.selectbox(
            "Domain",
            ["All", "retail", "finance", "hr", "logistics", "saas", "generic"]
        )
    with col_f2:
        template_filter = st.selectbox(
            "Template type",
            ["All", "revenue_analysis", "invoice_analysis",
             "product_analysis", "customer_analysis"]
        )
    with col_f3:
        search_query = st.text_input("Search model name", placeholder="e.g. revenue, customer...")

    # ── Model list ─────────────────────────────────────────────────────────────
    try:
        models = get_all_models(
            domain        = None if domain_filter == "All" else domain_filter,
            template_type = None if template_filter == "All" else template_filter
        )

        if search_query:
            models = [m for m in models if search_query.lower() in m["name"].lower()]

        if not models:
            st.info("No models found matching filters.")
        else:
            st.markdown(f"**{len(models)} model(s) found**")

            for model in models:
                score      = model["quality_score"]
                score_col  = "#22c55e" if score >= 80 else ("#f59e0b" if score >= 50 else "#ef4444")
                run_count  = model["run_count"]
                last_used  = model.get("last_used", "never")[:10] if model.get("last_used") else "never"

                with st.expander(
                    f"📄 {model['name']}  "
                    f"[{model['domain']}] [{model['template_type']}]"
                ):
                    col_meta, col_sql = st.columns([1, 2])

                    with col_meta:
                        st.markdown(
                            f"**Quality:** <span style='color:{score_col}'>{score}/100</span>",
                            unsafe_allow_html=True
                        )
                        st.markdown(f"**Times used:** {run_count}")
                        st.markdown(f"**Last used:** {last_used}")
                        st.markdown(f"**Template:** {model['template_type']}")

                        try:
                            hints = json.loads(model.get("table_hints", "[]"))
                            st.markdown(f"**Tables:** {', '.join(hints)}")
                        except Exception:
                            pass

                        # Quality score editor
                        new_score = st.slider(
                            "Adjust quality",
                            0, 100,
                            int(score),
                            key=f"reg_score_{model['id']}"
                        )
                        if st.button("Save", key=f"reg_save_{model['id']}"):
                            update_quality_score(model["name"], new_score)
                            st.success("Updated")

                    with col_sql:
                        st.code(model["sql"], language="sql")

    except Exception as e:
        st.error(f"Error loading registry: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — RUN HISTORY
# ═══════════════════════════════════════════════════════════════════════════════

elif "📊 Run History" in page:

    st.title("📊 Run History")
    st.markdown("Every pipeline execution is logged here with full metrics.")

    try:
        runs = get_run_history(limit=50)

        if not runs:
            st.info("No runs yet. Execute the pipeline to see history.")
        else:
            # Summary stats
            total      = len(runs)
            successful = sum(1 for r in runs if r["dbt_success"])
            avg_trust  = sum(r["trust_score"] for r in runs) / total if total else 0
            total_healed = sum(r["models_healed"] for r in runs)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total runs",        total)
            c2.metric("Successful",        f"{successful}/{total}")
            c3.metric("Avg trust score",   f"{avg_trust:.1f}/100")
            c4.metric("Models auto-healed", total_healed)

            st.markdown("---")

            # Run table
            for run in runs:
                status     = "✅ SUCCESS" if run["dbt_success"] else "❌ FAILED"
                drift      = "⚠ Drift detected" if run["drift_detected"] else "No drift"
                trust_col  = "#22c55e" if run["trust_score"] >= 80 else "#f59e0b"
                run_date   = run["run_at"][:19].replace("T", " ")

                try:
                    tables = json.loads(run["client_schema"])
                    schema_str = ", ".join(tables[:4])
                    if len(tables) > 4:
                        schema_str += f" +{len(tables)-4} more"
                except Exception:
                    schema_str = "unknown"

                st.markdown(
                    f"""<div style='background:#1e293b; border-radius:8px; padding:14px 18px;
                                    margin-bottom:8px; border-left:4px solid
                                    {"#22c55e" if run["dbt_success"] else "#ef4444"};'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div>
                                <strong style='color:#e2e8f0'>{run_date}</strong>
                                <span style='color:#64748b; margin-left:12px; font-size:0.85rem'>
                                    {schema_str}
                                </span>
                            </div>
                            <div style='text-align:right'>
                                <span style='color:{"#22c55e" if run["dbt_success"] else "#ef4444"};
                                             font-weight:700'>{status}</span>
                            </div>
                        </div>
                        <div style='margin-top:8px; display:flex; gap:24px; font-size:0.85rem;
                                    color:#94a3b8'>
                            <span>📦 {run["models_built"]} models</span>
                            <span>🔧 {run["models_healed"]} healed</span>
                            <span>🎯 <span style='color:{trust_col}'>{run["trust_score"]:.1f}/100</span> trust</span>
                            <span>{'⚠️ ' + drift if run["drift_detected"] else '✓ ' + drift}</span>
                        </div>
                    </div>""",
                    unsafe_allow_html=True
                )

    except Exception as e:
        st.error(f"Error loading run history: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

elif "⚙️ Settings" in page:

    st.title("⚙️ Settings")

    tab1, tab2, tab3 = st.tabs(["LLM Configuration", "Snowflake Connection", "Registry"])

    with tab1:
        st.subheader("LLM Backend")
        st.markdown("""
        Configure your LLM backend in the `.env` file in the project root.

        **Option 1 — Groq (recommended, free cloud)**
        ```
        LLM_BACKEND=groq
        GROQ_API_KEY=your_key_here
        GROQ_MODEL=llama-3.1-8b-instant
        ```
        Get a free API key at [console.groq.com](https://console.groq.com) — no credit card required.
        14,400 free requests/day.

        **Option 2 — Ollama (local, fully offline)**
        ```
        LLM_BACKEND=ollama
        OLLAMA_MODEL=llama3.1
        ```
        Install from [ollama.com](https://ollama.com), then run:
        ```bash
        ollama pull llama3.1
        ```
        """)

        # Current status
        try:
            info = get_backend_info()
            st.success(
                f"Currently using: **{info['backend'].upper()}** — {info['model']}"
            )
        except Exception as e:
            st.error(f"LLM not configured: {e}")

    with tab2:
        st.subheader("Snowflake Connection")
        st.markdown("""
        Set these in your `.env` file:
        ```
        SNOWFLAKE_USER=your_username
        SNOWFLAKE_PASSWORD=your_password
        SNOWFLAKE_ACCOUNT=your_account
        SNOWFLAKE_WAREHOUSE=COMPUTE_WH
        SNOWFLAKE_DATABASE=your_database
        SNOWFLAKE_SCHEMA=RAW
        SNOWFLAKE_ROLE=ACCOUNTADMIN
        ```
        """)

        # Show current values (masked)
        fields = [
            "SNOWFLAKE_USER", "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
            "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_ROLE"
        ]
        for field in fields:
            val = os.getenv(field, "")
            status = "✅ Set" if val else "❌ Missing"
            st.markdown(f"**{field}:** {status}")

    with tab3:
        st.subheader("Model Registry")

        try:
            stats = get_stats()
            st.json(stats)
        except Exception:
            st.info("Registry not initialised yet.")

        st.markdown("---")
        st.markdown("**Registry database location:**")
        from registry.model_registry import DB_PATH
        st.code(DB_PATH)

        if st.button("🗑 Clear registry (cannot be undone)", type="secondary"):
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                st.success("Registry cleared.")
            else:
                st.info("Registry is already empty.")

        st.markdown("---")
        st.subheader("Export registry")
        try:
            models = get_all_models()
            if models:
                export_data = json.dumps(models, indent=2)
                st.download_button(
                    "⬇ Download registry as JSON",
                    export_data,
                    file_name=f"registry_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        except Exception:
            st.info("No models to export.")
