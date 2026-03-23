import snowflake.connector


def profile_table(cursor, table_name, columns, database, schema):
    """
    For a given table, compute:
    - row count
    - null percentage per column
    - distinct count for _id columns (cardinality check)
    """

    profile = {
        "table": table_name,
        "row_count": 0,
        "columns": {}
    }

    # Row count
    try:
        cursor.execute(f'SELECT COUNT(*) FROM "{database}"."{schema}"."{table_name}"')
        profile["row_count"] = cursor.fetchone()[0]
    except Exception as e:
        print(f"  Could not count rows for {table_name}: {e}")
        return profile

    if profile["row_count"] == 0:
        return profile

    for col in columns:
        col_name = col["column"]
        col_type = col["type"]
        col_stats = {"type": col_type, "null_pct": None, "distinct_count": None}

        # Null percentage
        try:
            cursor.execute(
                f'SELECT ROUND(100.0 * SUM(CASE WHEN "{col_name}" IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) '
                f'FROM "{database}"."{schema}"."{table_name}"'
            )
            col_stats["null_pct"] = cursor.fetchone()[0]
        except Exception:
            pass

        # Distinct count for ID columns or low-cardinality text
        if col_name.lower().endswith("_id") or col_type.upper() in ("TEXT", "VARCHAR", "STRING"):
            try:
                cursor.execute(
                    f'SELECT COUNT(DISTINCT "{col_name}") FROM "{database}"."{schema}"."{table_name}"'
                )
                col_stats["distinct_count"] = cursor.fetchone()[0]
            except Exception:
                pass

        profile["columns"][col_name] = col_stats

    return profile


def run_data_profiling(connection_params, schema):
    """
    Profile all tables in the schema.
    Returns list of profile dicts.
    """

    print("\nRunning data profiling...")

    database = connection_params.get("database", "")
    raw_schema = connection_params.get("schema", "")

    profiles = []

    try:
        conn = snowflake.connector.connect(**connection_params)
        cursor = conn.cursor()

        for table_name, columns in schema.items():
            print(f"  Profiling {table_name}...")
            profile = profile_table(cursor, table_name, columns, 'SOURCE', 'AI_RAW')
            profiles.append(profile)

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Data profiling failed: {e}")

    return profiles


def score_trust(profiles):
    """
    Compute a data trust score (0-100) per table based on null rates.
    Also flags columns with >20% nulls as quality warnings.
    """

    scored = []

    for profile in profiles:
        warnings = []
        total_null_pct = 0
        col_count = 0

        for col_name, stats in profile["columns"].items():
            null_pct = stats.get("null_pct")
            if null_pct is not None:
                total_null_pct += null_pct
                col_count += 1
                if null_pct > 20:
                    warnings.append(f"{col_name}: {null_pct}% nulls")

        avg_null_pct = (total_null_pct / col_count) if col_count > 0 else 0
        trust_score = round(max(0, 100 - avg_null_pct), 1)

        scored.append({
            "table": profile["table"],
            "row_count": profile["row_count"],
            "trust_score": trust_score,
            "avg_null_pct": round(avg_null_pct, 2),
            "warnings": warnings,
            "columns": profile["columns"]
        })

    return scored


def print_profile_summary(scored_profiles):
    print("\n" + "=" * 50)
    print("DATA QUALITY REPORT")
    print("=" * 50)

    for p in scored_profiles:
        score = p["trust_score"]
        emoji = "✅" if score >= 80 else ("⚠️" if score >= 50 else "❌")
        print(f"\n{emoji}  {p['table']}")
        print(f"     Rows: {p['row_count']:,}  |  Trust score: {score}/100  |  Avg nulls: {p['avg_null_pct']}%")
        if p["warnings"]:
            for w in p["warnings"]:
                print(f"     ⚠  {w}")

    print("=" * 50 + "\n")
