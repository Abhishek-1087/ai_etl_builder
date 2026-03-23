import re

def _strip_inline_comments(sql):
    """Remove -- comments that contain prose explanations."""
    lines = []
    for line in sql.split("\n"):
        # Keep pure SQL comment lines (short ones like -- alias)
        # Remove long explanation comments
        cleaned = re.sub(r"--\s*.{40,}", "", line)
        lines.append(cleaned.rstrip())
    return "\n".join(lines)

def convert_to_dbt(sql, layer="mart"):
    """
    Takes plain SQL and converts it to a valid dbt model.
    Handles: config block, source() → ref(), raw table names → stg_ refs,
    alias injection, and SQL cleanup.
    """

    sql = _strip_noise(sql)
    sql = _strip_inline_comments(sql)
    sql = _remove_create_statements(sql)
    sql = _convert_table_refs(sql)
    sql = _ensure_aliases(sql)
    sql = _fix_ref_syntax(sql)

    materialized = "table" if layer == "mart" else "view"
    config = f"{{{{ config(materialized='{materialized}') }}}}"

    # Only add config if not already present
    if "config(materialized" not in sql:
        sql = config + "\n\n" + sql

    return sql.strip()


def _strip_noise(sql):
    """Remove markdown, explanations, and leading/trailing prose."""

    # Strip markdown fences
    sql = sql.replace("```sql", "").replace("```", "")

    lines = sql.split("\n")
    result = []
    started = False

    for line in lines:
        stripped = line.strip()

        # Start capturing from first SQL keyword or jinja block
        if not started:
            if re.match(
                r"^(SELECT|WITH|{{|{%|--)",
                stripped, re.IGNORECASE
            ):
                started = True
            else:
                continue

        # Stop at prose lines after SQL has started
        if started and stripped:
            is_prose = (
                stripped[0].isupper()
                and not re.search(
                    r"^(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|GROUP|ORDER|HAVING|WITH|ON|AND|OR|UNION|LIMIT|--)",
                    stripped, re.IGNORECASE
                )
                and not re.search(r"[,\(\)=\.\*<>]", stripped)
                and len(stripped.split()) > 5
            )
            if is_prose:
                break

        result.append(line)

    return "\n".join(result).strip()


def _remove_create_statements(sql):
    """Remove CREATE TABLE/VIEW wrappers that LLM sometimes generates."""

    sql = re.sub(
        r"CREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW)\s+\S+\s+AS\s*",
        "", sql, flags=re.IGNORECASE
    )
    # Remove trailing semicolons
    sql = sql.rstrip().rstrip(";").strip()
    return sql

def _convert_table_refs(sql):
    protected = {}
    counter   = [0]

    def protect(m):
        key = f"__REF_{counter[0]}__"
        protected[key] = m.group(0)
        counter[0] += 1
        return key

    # Protect already-wrapped {{ ref(...) }} blocks
    sql = re.sub(r"\{\{[^}]+\}\}", protect, sql)

    # FROM/JOIN schema.table (real dot) → ref('stg_table')
    # Extra guard: don't match __PLACEHOLDER__ patterns
    def schema_dot_to_ref(m):
        keyword = m.group(1)
        table   = m.group(3).lower()
        # Skip placeholders
        if table.startswith("_") or table.startswith("ref"):
            return m.group(0)
        if not table.startswith("stg_"):
            table = f"stg_{table}"
        return f"{keyword} {{{{ ref('{table}') }}}}"

    sql = re.sub(
        r"(FROM|JOIN)(\s+)\w+\.(\w+)\b(?!\s*\()",
        schema_dot_to_ref, sql, flags=re.IGNORECASE
    )

    # FROM/JOIN bare table (no dot)
    def bare_to_ref(m):
        keyword = m.group(1)
        space   = m.group(2)
        table   = m.group(3).lower()
        # Skip placeholders and very short names (aliases)
        if table.startswith("_") or len(table) <= 2:
            return m.group(0)
        if not table.startswith("stg_"):
            table = f"stg_{table}"
        return f"{keyword}{space}{{{{ ref('{table}') }}}}"

    sql = re.sub(
        r"(FROM|JOIN)(\s+)(?!\{\{)([a-zA-Z_][a-zA-Z0-9_]*)\b(?!\s*\()",
        bare_to_ref, sql, flags=re.IGNORECASE
    )

    # Restore protected refs
    for key, val in protected.items():
        sql = sql.replace(key, val)

    return sql

def _ensure_aliases(sql):
    """
    Make sure every FROM and JOIN table reference has a short alias.
    If {{ ref('stg_customer') }} has no alias after it, inject one.
    """

    def make_alias(table_name):
        # stg_customer → c, stg_order_detail → od
        parts = table_name.replace("stg_", "").split("_")
        return "".join(p[0] for p in parts if p)

    def inject_alias(m):
        full_ref = m.group(1)   # {{ ref('stg_customer') }}
        after    = m.group(2)   # whatever comes after

        # Extract table name from ref
        name_match = re.search(r"ref\('([^']+)'\)", full_ref)
        if not name_match:
            return m.group(0)

        table_name = name_match.group(1)
        alias = make_alias(table_name)

        # If what follows is already an alias (a word, not ON/WHERE/JOIN/,)
        already_aliased = re.match(r"^\s+\w+\s", after) and not re.match(
            r"^\s+(ON|WHERE|LEFT|RIGHT|INNER|JOIN|GROUP|ORDER|HAVING|,)\b",
            after, re.IGNORECASE
        )
        if already_aliased:
            return m.group(0)

        return f"{full_ref} {alias}{after}"

    # FROM {{ ref(...) }} — inject alias if missing
    sql = re.sub(
        r"(FROM\s+\{\{[^}]+\}\})(\s)",
        lambda m: inject_alias(m) if "ref(" in m.group(1) else m.group(0),
        sql, flags=re.IGNORECASE
    )

    # JOIN {{ ref(...) }} — inject alias if missing  
    sql = re.sub(
        r"(JOIN\s+\{\{[^}]+\}\})(\s)",
        lambda m: inject_alias(m) if "ref(" in m.group(1) else m.group(0),
        sql, flags=re.IGNORECASE
    )

    return sql


def _fix_ref_syntax(sql):
    """Fix malformed {{ ref() }} patterns the LLM commonly produces."""

    # Nested ref: {{ ref('{{ ref('x') }}') }} → {{ ref('x') }}
    sql = re.sub(
        r"\{\{\s*ref\('\{\{\s*ref\('([^']+)'\)\s*\}\}'\)\s*\}\}",
        r"{{ ref('\1') }}", sql
    )
    # Extra closing brackets
    sql = re.sub(r"\}\}'\)\s*\}\}", "}}", sql)
    sql = re.sub(r"\}\}'\)", "}}", sql)

    # Single braces: { ref( → {{ ref(
    sql = re.sub(r"(?<!\{)\{(?!\{)\s*ref\(", "{{ ref(", sql)
    sql = re.sub(r"\)\s*\}(?!\})", ") }}", sql)

    return sql