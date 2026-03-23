"""
Schema Adaptor
--------------
Takes a model retrieved from the registry (built for a different schema)
and adapts its SQL to work with the current client's schema.

This is what makes the registry useful — retrieved models are never used
as-is. Column names, table references, and aliases are remapped to match
whatever columns actually exist in the current Snowflake instance.
"""

import re


def adapt_model(sql: str, current_schema: dict) -> tuple[str, float]:
    """
    Adapt a registry model's SQL to the current schema.

    Returns (adapted_sql, confidence_score).
    confidence_score 0.0-1.0:
        1.0 = perfect match, no changes needed
        0.7+ = good match, minor column remapping
        0.5-0.7 = partial match, some columns substituted
        <0.5 = poor match, likely needs manual review

    Strategy:
    1. Extract all {{ ref('stg_xxx') }} calls from stored SQL
    2. Map each stg_xxx to best matching table in current schema
    3. For each column reference, find closest match in mapped table
    4. Rewrite SQL with new table/column names
    """

    current_tables = {t.lower(): cols for t, cols in current_schema.items()}
    current_col_names = {
        t: [c["column"].lower() for c in cols]
        for t, cols in current_schema.items()
    }

    # Step 1: find all table refs in stored SQL
    stored_refs = list(set(re.findall(r"ref\('(stg_\w+)'\)", sql)))
    if not stored_refs:
        return sql, 0.5

    # Step 2: map stored tables to current tables
    table_map = {}
    for stored_table in stored_refs:
        best_match, best_score = _find_best_table(stored_table, current_tables)
        if best_match:
            table_map[stored_table] = best_match

    if not table_map:
        return sql, 0.2

    # Step 3: remap table references in SQL
    adapted = sql
    for stored, current in table_map.items():
        if stored != current:
            adapted = adapted.replace(f"ref('{stored}')", f"ref('{current}')")
            # Also update aliases derived from old table name
            old_alias = _alias(stored)
            new_alias = _alias(current)
            if old_alias != new_alias:
                adapted = _replace_alias(adapted, old_alias, new_alias)

    # Step 4: remap column references
    adapted, col_confidence = _remap_columns(adapted, table_map, current_col_names)

    # Step 5: calculate overall confidence
    table_confidence = len(table_map) / max(len(stored_refs), 1)
    confidence = (table_confidence * 0.6) + (col_confidence * 0.4)

    return adapted, round(confidence, 2)


def _find_best_table(stored_table: str, current_tables: dict) -> tuple:
    """
    Find the best matching table in current schema for a stored table reference.
    Uses substring matching on the table name (minus stg_ prefix).
    """
    stored_base = stored_table.replace("stg_", "").lower()
    stored_words = stored_base.split("_")

    best_table = None
    best_score = 0

    for current_table in current_tables.keys():
        current_base = current_table.replace("stg_", "").lower()
        current_words = current_base.split("_")

        # Exact match
        if stored_base == current_base:
            return current_table, 1.0

        # Word overlap score
        overlap = len(set(stored_words) & set(current_words))
        score = overlap / max(len(stored_words), len(current_words))

        # Partial name match
        if stored_base in current_base or current_base in stored_base:
            score = max(score, 0.7)

        if score > best_score:
            best_score = score
            best_table = current_table

    return best_table, best_score


def _remap_columns(sql: str, table_map: dict, current_col_names: dict) -> tuple:
    """
    Find column references in SQL that don't exist in the current schema
    and substitute the closest matching column name.
    Returns (adapted_sql, confidence_score).
    """

    remapped = 0
    failed   = 0
    total    = 0

    # Build alias → table mapping for column lookup
    alias_to_table = {}
    for stored, current in table_map.items():
        alias = _alias(current)
        alias_to_table[alias] = current

    # Find alias.column patterns and validate/remap
    def remap_col(m):
        nonlocal remapped, failed, total
        alias  = m.group(1)
        column = m.group(2).lower()
        full   = m.group(0)

        total += 1
        table = alias_to_table.get(alias)
        if not table:
            return full

        available_cols = current_col_names.get(table, [])
        if not available_cols:
            return full

        # Column exists — no change needed
        if column in available_cols:
            return full

        # Find best matching column
        best_col = _find_best_column(column, available_cols)
        if best_col:
            remapped += 1
            return f"{alias}.{best_col}"

        failed += 1
        return full

    adapted = re.sub(r"\b([a-z]+)\.([a-z][a-z0-9_]+)\b", remap_col, sql)

    if total == 0:
        return adapted, 0.8

    confidence = max(0, (total - failed) / total)
    return adapted, round(confidence, 2)


def _find_best_column(stored_col: str, available_cols: list) -> str:
    """Find the best matching column from available list."""

    stored_words = stored_col.split("_")

    best_col   = None
    best_score = 0

    for col in available_cols:
        # Exact match
        if col == stored_col:
            return col

        col_words = col.split("_")
        overlap   = len(set(stored_words) & set(col_words))
        score     = overlap / max(len(stored_words), len(col_words))

        # Suffix match (both end in _id, _date, _inr, etc.)
        if stored_col.split("_")[-1] == col.split("_")[-1]:
            score = max(score, 0.5)

        if score > best_score:
            best_score = score
            best_col = col

    return best_col if best_score >= 0.4 else None


def _alias(table_name: str) -> str:
    """stg_order_item → oi"""
    parts = table_name.replace("stg_", "").split("_")
    return "".join(p[0] for p in parts if p)


def _replace_alias(sql: str, old_alias: str, new_alias: str) -> str:
    """
    Replace all occurrences of alias.column with new_alias.column.
    Only replaces when alias appears as a standalone word before a dot.
    """
    if old_alias == new_alias:
        return sql

    # Match alias at word boundary followed by dot
    pattern = r"\b" + re.escape(old_alias) + r"\."
    return re.sub(pattern, f"{new_alias}.", sql)


def score_match(stored_hints: list, current_schema: dict) -> float:
    """
    Quick pre-search scoring — how well does a stored model's table hints
    match the current schema? Used to rank registry results before
    doing full adaptation.
    """
    current_tables = [t.lower() for t in current_schema.keys()]
    current_cols   = []
    for cols in current_schema.values():
        current_cols.extend(c["column"].lower() for c in cols)

    if not stored_hints:
        return 0.0

    matches = sum(
        1 for hint in stored_hints
        if any(ct in hint or hint in ct for ct in current_tables)
    )
    return matches / len(stored_hints)
