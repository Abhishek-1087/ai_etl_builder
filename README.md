# AI-Native Agentic ETL Builder
### with Self-Healing Pipelines + Model Registry

---

## What this does

Automatically builds and maintains Snowflake + dbt analytics pipelines.
Every successful run stores models in a registry — next client with a
similar schema gets adapted versions instead of generating from scratch.

---

## Project structure

```
ai_etl_builder/
├── main.py                          # Pipeline entry point
├── .env                             # Your credentials (copy from .env.example)
├── requirements.txt
│
├── agent/                           # Pipeline agents
│   ├── llm.py                       # LLM router (Groq + Ollama)
│   ├── schema_reader.py             # Reads Snowflake INFORMATION_SCHEMA
│   ├── schema_drift_detector.py     # Detects schema changes between runs
│   ├── data_profiler.py             # Null rates, trust scores per table
│   ├── join_detector.py             # Infers FK relationships
│   ├── schema_context.py            # Formats schema for LLM prompts
│   ├── staging_model_generator.py   # Auto-generates stg_* dbt views
│   ├── staging_view_reader.py       # Lists staging views in Snowflake
│   ├── insight_planner.py           # LLM plans analytics mart names
│   ├── mart_generator.py            # Builds mart SQL from 4 generic templates
│   ├── dbt_model_creator.py         # Writes SQL files to dbt_project/
│   ├── self_healing_runner.py       # Runs dbt, heals failures (3 retries)
│   ├── auto_heal_agent.py           # LLM SQL fixer
│   └── dashboard_reporter.py        # Generates HTML + JSON run report
│
├── registry/                        # Model Registry (new)
│   ├── model_registry.py            # SQLite store for dbt models
│   ├── schema_adaptor.py            # Adapts stored models to new schemas
│   └── composition_agent.py        # Registry-first mart composer
│
├── ui/                              # Review UI (new)
│   └── app.py                       # Streamlit dashboard
│
└── dbt_project/                     # dbt project
    ├── dbt_project.yml
    ├── models/
    │   ├── staging/                 # Auto-generated stg_* views
    │   └── mart/                    # Auto-generated mart tables
    └── macros/
        ├── replace_null.sql
        └── generate_schema_name.sql
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure credentials
```bash
cp .env.example .env
# Edit .env with your Snowflake credentials and Groq API key
```

### 3. Get a free Groq API key
Go to https://console.groq.com — no credit card required.
14,400 free requests/day. Much better SQL quality than local models.

Add to .env:
```
LLM_BACKEND=groq
GROQ_API_KEY=your_key_here
```

### 4. Configure dbt profile
Edit `~/.dbt/profiles.yml`:
```yaml
dbt_project:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE') }}"
      database: "{{ env_var('SNOWFLAKE_DATABASE') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE') }}"
      schema: RAW
      threads: 4
```

---

## Running the pipeline

### Full auto-run
```bash
python main.py
```
Runs all 9 steps, auto-approves all models, saves successful ones to registry.

### Human-in-the-loop (recommended)
```bash
# Step 1: Run pipeline up to mart generation
python main.py --review

# Step 2: Open review UI, approve/reject models
streamlit run ui/app.py

# Step 3: Execute dbt with only approved models
python main.py --execute
```

---

## How the registry works

1. First run: LLM generates all mart models from scratch
2. Models saved to `registry/registry.db` (SQLite, on your machine)
3. Second client with similar schema:
   - Composition agent searches registry
   - Finds matching models, adapts column names to new schema
   - Only calls LLM for insights with no registry match
4. Over time: registry hit rate increases, LLM costs decrease

The registry compounds in value — every engagement makes the next one faster.

---

## Adding your own templates

Edit `agent/mart_generator.py` — add an entry to `TEMPLATE_RULES`:

```python
{
    "keywords": ["your", "insight", "keywords"],
    "template": "revenue_analysis",   # or invoice/product/customer
    "primary":  ["your_primary_table"],
    "joins":    [{"hints": ["related_table"], "key": "join_column", "role": "dimension"}],
    "metric_hints":    ["amount_col", "value_col"],
    "dimension_hints": ["group_by_col", "category_col"],
    "date_hints":      ["date_col"],
}
```

No code changes needed in the template builders — they're fully generic.
