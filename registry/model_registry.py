"""
Model Registry
--------------
Stores dbt mart models with their schema fingerprints and metadata.
Uses SQLite for structured storage and sentence-transformers for
vector similarity search — no external services required.

Every successful dbt run feeds models back into the registry.
Next client with a similar schema gets adapted versions instead of
generating from scratch.
"""

import sqlite3
import json
import hashlib
import os
from datetime import datetime


DB_PATH = os.path.join(os.path.dirname(__file__), "registry.db")


# ── Database setup ────────────────────────────────────────────────────────────

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS models (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            domain          TEXT NOT NULL,
            template_type   TEXT NOT NULL,
            sql             TEXT NOT NULL,
            schema_fingerprint TEXT NOT NULL,
            table_hints     TEXT NOT NULL,
            column_hints    TEXT NOT NULL,
            quality_score   REAL DEFAULT 100.0,
            run_count       INTEGER DEFAULT 1,
            last_used       TEXT,
            created_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at          TEXT NOT NULL,
            client_schema   TEXT NOT NULL,
            models_built    INTEGER DEFAULT 0,
            models_healed   INTEGER DEFAULT 0,
            trust_score     REAL DEFAULT 0,
            dbt_success     INTEGER DEFAULT 0,
            drift_detected  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS schema_snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint     TEXT UNIQUE NOT NULL,
            domain          TEXT NOT NULL,
            table_names     TEXT NOT NULL,
            column_summary  TEXT NOT NULL,
            first_seen      TEXT NOT NULL,
            times_seen      INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_models_domain
            ON models(domain);
        CREATE INDEX IF NOT EXISTS idx_models_template
            ON models(template_type);
        CREATE INDEX IF NOT EXISTS idx_models_fingerprint
            ON models(schema_fingerprint);
    """)
    conn.commit()
    conn.close()
    print(f"Registry initialised at {DB_PATH}")


# ── Schema fingerprinting ─────────────────────────────────────────────────────

def fingerprint_schema(schema: dict) -> str:
    """
    Create a stable fingerprint from table+column patterns.
    Two schemas with similar table/column names produce similar fingerprints.
    Uses sorted canonical form so column order doesn't matter.
    """
    parts = []
    for table in sorted(schema.keys()):
        cols = sorted(c["column"].lower() for c in schema[table])
        parts.append(f"{table.lower()}:{','.join(cols)}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def schema_to_text(schema: dict) -> str:
    """
    Convert schema dict to a text representation for similarity matching.
    Format: 'table1 col1 col2 col3 | table2 col1 col2'
    """
    parts = []
    for table in sorted(schema.keys()):
        cols = sorted(c["column"].lower() for c in schema[table])
        parts.append(f"{table.lower()} {' '.join(cols)}")
    return " | ".join(parts)


def detect_domain(schema: dict) -> str:
    """
    Classify the schema into a business domain based on table names.
    Returns one of: retail, finance, hr, logistics, generic.
    """
    tables = " ".join(schema.keys()).lower()

    domain_keywords = {
        "retail":    ["order", "product", "customer", "cart", "inventory", "item"],
        "finance":   ["invoice", "payment", "ledger", "transaction", "account", "budget"],
        "hr":        ["employee", "payroll", "leave", "attendance", "department", "salary"],
        "logistics": ["shipment", "delivery", "warehouse", "route", "carrier", "tracking"],
        "saas":      ["subscription", "user", "plan", "feature", "tenant", "billing"],
    }

    scores = {domain: 0 for domain in domain_keywords}
    for domain, keywords in domain_keywords.items():
        scores[domain] = sum(1 for kw in keywords if kw in tables)

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "generic"


# ── Model storage ─────────────────────────────────────────────────────────────

def save_model(name: str, sql: str, schema: dict, template_type: str,
               quality_score: float = 100.0):
    """
    Store a successfully compiled dbt model in the registry.
    Extracts table hints and column hints from the SQL for future retrieval.
    """
    init_db()
    conn = get_connection()

    domain      = detect_domain(schema)
    fingerprint = fingerprint_schema(schema)

    # Extract table and column hints from SQL for keyword search
    import re
    table_hints  = list(set(re.findall(r"ref\('(stg_\w+)'\)", sql)))
    column_hints = list(set(re.findall(r"\b([a-z][a-z0-9_]+_(?:id|date|inr|amount|total|qty|count|pct|name|type|status))\b", sql)))

    now = datetime.utcnow().isoformat()

    # Upsert — update if same name+fingerprint already exists
    existing = conn.execute(
        "SELECT id, run_count FROM models WHERE name = ? AND schema_fingerprint = ?",
        (name, fingerprint)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE models
            SET sql = ?, quality_score = ?, run_count = run_count + 1, last_used = ?
            WHERE id = ?
        """, (sql, quality_score, now, existing["id"]))
        print(f"  Registry: updated '{name}' (run #{existing['run_count'] + 1})")
    else:
        conn.execute("""
            INSERT INTO models
                (name, domain, template_type, sql, schema_fingerprint,
                 table_hints, column_hints, quality_score, run_count, last_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            name, domain, template_type, sql, fingerprint,
            json.dumps(table_hints), json.dumps(column_hints),
            quality_score, now, now
        ))
        print(f"  Registry: saved new model '{name}' [{domain}]")

    conn.commit()
    conn.close()


def save_run(schema: dict, models_built: int, models_healed: int,
             trust_score: float, dbt_success: bool, drift_detected: bool):
    """Log a pipeline run to the registry."""
    init_db()
    conn = get_connection()
    conn.execute("""
        INSERT INTO runs
            (run_at, client_schema, models_built, models_healed,
             trust_score, dbt_success, drift_detected)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.utcnow().isoformat(),
        json.dumps(list(schema.keys())),
        models_built, models_healed,
        trust_score,
        1 if dbt_success else 0,
        1 if drift_detected else 0
    ))
    conn.commit()
    conn.close()


# ── Model search ──────────────────────────────────────────────────────────────

def search_models(schema: dict, template_type: str = None,
                  limit: int = 10) -> list:
    """
    Search registry for models matching the current schema.
    Uses keyword overlap on table_hints and column_hints.
    Returns list of dicts sorted by relevance score.
    """
    init_db()
    conn = get_connection()

    # Build search terms from current schema
    current_tables = [t.lower() for t in schema.keys()]
    current_cols   = []
    for cols in schema.values():
        current_cols.extend(c["column"].lower() for c in cols)
    current_cols = list(set(current_cols))

    query = "SELECT * FROM models WHERE quality_score >= 50"
    params = []
    if template_type:
        query += " AND template_type = ?"
        params.append(template_type)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # Score each model by overlap with current schema
    scored = []
    for row in rows:
        stored_tables = json.loads(row["table_hints"])
        stored_cols   = json.loads(row["column_hints"])

        # Table overlap score (weighted higher)
        table_overlap = sum(
            1 for t in stored_tables
            if any(ct in t for ct in current_tables)
        )
        # Column overlap score
        col_overlap = sum(
            1 for c in stored_cols
            if c in current_cols
        )

        relevance = (table_overlap * 3) + col_overlap

        if relevance > 0:
            scored.append({
                "id":            row["id"],
                "name":          row["name"],
                "domain":        row["domain"],
                "template_type": row["template_type"],
                "sql":           row["sql"],
                "quality_score": row["quality_score"],
                "run_count":     row["run_count"],
                "relevance":     relevance,
                "table_hints":   stored_tables,
                "column_hints":  stored_cols,
            })

    scored.sort(key=lambda x: (x["relevance"], x["quality_score"]), reverse=True)
    return scored[:limit]


def get_all_models(domain: str = None, template_type: str = None) -> list:
    """Fetch all models, optionally filtered by domain or template."""
    init_db()
    conn = get_connection()

    query = "SELECT * FROM models WHERE 1=1"
    params = []
    if domain:
        query += " AND domain = ?"
        params.append(domain)
    if template_type:
        query += " AND template_type = ?"
        params.append(template_type)
    query += " ORDER BY quality_score DESC, run_count DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run_history(limit: int = 20) -> list:
    """Fetch recent pipeline runs."""
    init_db()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY run_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_quality_score(model_name: str, new_score: float):
    """Called by self-healer to lower score on repeated failures."""
    init_db()
    conn = get_connection()
    conn.execute(
        "UPDATE models SET quality_score = ? WHERE name = ?",
        (new_score, model_name)
    )
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """Return high-level registry statistics for the dashboard."""
    init_db()
    conn = get_connection()

    total_models = conn.execute("SELECT COUNT(*) FROM models").fetchone()[0]
    total_runs   = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    avg_score    = conn.execute("SELECT AVG(quality_score) FROM models").fetchone()[0] or 0
    domains      = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM models GROUP BY domain"
    ).fetchall()
    templates    = conn.execute(
        "SELECT template_type, COUNT(*) as cnt FROM models GROUP BY template_type"
    ).fetchall()
    recent_runs  = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE dbt_success = 1"
    ).fetchone()[0]

    conn.close()
    return {
        "total_models":   total_models,
        "total_runs":     total_runs,
        "avg_quality":    round(avg_score, 1),
        "success_runs":   recent_runs,
        "by_domain":      {r["domain"]: r["cnt"] for r in domains},
        "by_template":    {r["template_type"]: r["cnt"] for r in templates},
    }
