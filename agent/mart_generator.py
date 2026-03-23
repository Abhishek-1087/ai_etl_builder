import re


# ── Template routing rules ────────────────────────────────────────────────────
# 4 generic templates. Any LLM-generated insight routes to one via keyword
# scoring. No insight names are hardcoded — routing is purely keyword-based.

TEMPLATE_RULES = [
    {
        "keywords": ["revenue", "performance", "region", "rep", "sales",
                     "quota", "channel", "discount", "delivery", "fulfil",
                     "order_value", "aov", "rep_performance", "rep_quota",
                     "order_status", "monthly_revenue", "daily_revenue"],
        "template": "revenue_analysis",
        "primary":  ["orders", "order"],
        "joins": [
            {"hints": ["customer"],           "key": "customer_id", "role": "dimension"},
            {"hints": ["sales_rep", "rep"],   "key": "rep_id",      "role": "dimension"},
            {"hints": ["order_item", "item"], "key": "order_id",    "role": "metric"},
        ],
        "metric_hints":    ["total_amount", "total_inr", "amount", "line_total"],
        "dimension_hints": ["city", "state", "segment", "region", "rep_id",
                            "channel", "status", "payment_method"],
        "date_hints":      ["order_date", "created"],
    },
    {
        "keywords": ["invoice", "payment", "paid", "unpaid", "billing",
                     "tax", "overdue", "countdown", "aging", "gst",
                     "receivable", "due", "collection"],
        "template": "invoice_analysis",
        "primary":  ["invoice"],
        "joins": [
            {"hints": ["customer"],        "key": "customer_id", "role": "dimension"},
            {"hints": ["orders", "order"], "key": "order_id",    "role": "context"},
        ],
        "metric_hints":    ["total_inr", "subtotal_inr", "amount", "tax_amount"],
        "dimension_hints": ["customer_id", "due_date", "invoice_date"],
        "date_hints":      ["invoice_date", "due_date"],
        "flag_hints":      ["is_paid"],
    },
    {
        "keywords": ["product", "item", "sku", "category", "ordered",
                     "popular", "sell", "mostly", "stock", "margin",
                     "catalogue", "assortment", "top_selling",
                     "monthly_product", "product_sales", "best_product"],
        "template": "product_analysis",
        "primary":  ["order_item", "item"],
        "joins": [
            {"hints": ["product"],         "key": "product_id", "role": "dimension"},
            {"hints": ["orders", "order"], "key": "order_id",   "role": "context"},
        ],
        "metric_hints":    ["quantity", "qty", "line_total", "unit_price"],
        "dimension_hints": ["product_id", "category"],
        "date_hints":      [],
    },
    {
        "keywords": ["customer", "segment", "signup", "acquisition",
                     "active", "churn", "trend", "retention", "new",
                     "cohort", "lifetime", "lapse", "inactive",
                     "total_active", "churn_rate", "segment_breakdown",
                     "customer_segment", "customer_churn", "breakdown"],
        "template": "customer_analysis",
        "primary":  ["customer"],
        "joins": [
            {"hints": ["orders", "order"], "key": "customer_id", "role": "metric"},
            {"hints": ["invoice"],         "key": "customer_id", "role": "metric"},
        ],
        "metric_hints":    ["customer_id"],
        "dimension_hints": ["segment", "city", "state", "signup_date"],
        "date_hints":      ["signup_date", "created_date"],
        "flag_hints":      ["is_active"],
    },
]


# ── Entry point ───────────────────────────────────────────────────────────────

def generate_mart(insight, schema_context, joins):
    """
    Generate a dbt mart model for the given insight name.
    Routes to one of 4 generic templates based on keyword scoring.
    All table/column names resolved dynamically from schema_context.
    Insight name passed through to template builders for sub-branching.
    """
    tables  = _parse_schema(schema_context)
    pattern = _match_pattern(insight)
    sql     = _build_from_pattern(pattern, tables, insight)
    sql     = _enforce_stg_refs(sql)

    return {
        "name":  f"mart_{insight}",
        "layer": "mart",
        "sql":   sql
    }


# ── Schema parser ─────────────────────────────────────────────────────────────

def _parse_schema(schema_context):
    """Parse schema_context string into {stg_table: [col, ...]} dict."""
    tables  = {}
    current = None
    for line in schema_context.split("\n"):
        line = line.strip()
        m = re.match(r"Table:\s*(stg_\w+)", line)
        if m:
            current = m.group(1)
            tables[current] = []
        elif current and line.startswith("- "):
            col = line[2:].split("(")[0].strip().lower()
            tables[current].append(col)
    return tables


# ── Pattern matcher ───────────────────────────────────────────────────────────

def _match_pattern(insight):
    """
    Score each template rule against insight keywords.
    Uses substring + word-level matching.
    Falls back to domain inference from insight name if no score > 0.
    """
    insight_lower = insight.lower()
    insight_words = set(insight_lower.split("_"))

    best, best_score = None, 0

    for rule in TEMPLATE_RULES:
        # Substring match score
        substring_score = sum(
            1 for kw in rule["keywords"]
            if kw in insight_lower
        )
        # Word-level overlap score
        rule_words  = set(" ".join(rule["keywords"]).split())
        word_score  = len(insight_words & rule_words) * 0.5
        score       = substring_score + word_score

        if score > best_score:
            best_score = score
            best = rule

    # No match — infer from name fragments
    if best_score == 0 or best is None:
        best = _infer_pattern_from_name(insight_lower)

    return best


def _infer_pattern_from_name(insight):
    """Last-resort: map name fragments to template."""
    fragment_map = [
        (["customer", "churn", "segment", "active", "signup",
          "retention", "cohort", "acquisition", "lapse", "breakdown"], 3),
        (["product", "item", "sku", "category", "sell",
          "margin", "stock", "catalogue", "top"], 2),
        (["invoice", "payment", "billing", "tax",
          "overdue", "aging", "receivable"], 1),
        (["revenue", "order", "sales", "rep", "quota",
          "channel", "discount", "region"], 0),
    ]
    for fragments, idx in fragment_map:
        if any(f in insight for f in fragments):
            return TEMPLATE_RULES[idx]
    return TEMPLATE_RULES[0]  # absolute fallback


# ── Utilities ─────────────────────────────────────────────────────────────────

def _find_col(cols, *hints):
    """Return first column whose name contains any hint substring."""
    for hint in hints:
        for col in cols:
            if hint in col:
                return col
    return None


def _find_table(tables, *hints):
    """Return first table name containing any hint substring."""
    for hint in hints:
        for t in tables:
            if hint in t:
                return t
    return None


def _alias(table_name):
    """stg_order_item → oi,  stg_customer → c,  stg_sales_rep → sr"""
    parts = table_name.replace("stg_", "").split("_")
    return "".join(p[0] for p in parts if p)


def _ref(table):
    """Always enforce stg_ prefix in ref() calls."""
    if not table.startswith("stg_"):
        table = f"stg_{table}"
    return f"{{{{ ref('{table}') }}}}"


def _enforce_stg_refs(sql):
    """Post-process SQL to ensure all ref() calls use stg_ prefix."""
    def fix_ref(m):
        table = m.group(1)
        if not table.startswith("stg_"):
            table = f"stg_{table}"
        return f"{{{{ ref('{table}') }}}}"
    return re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", fix_ref, sql)


def _resolve_joins(join_rules, tables, primary_cols):
    """
    For each join rule, locate the actual table and verify FK exists.
    Returns list of (table, alias, cols, join_key, role).
    Silently skips joins whose table or key cannot be found.
    """
    resolved = []
    for jr in join_rules:
        jt = _find_table(tables, *jr["hints"])
        if not jt:
            continue
        jkey = jr["key"]
        if not _find_col(primary_cols, jkey):
            continue
        resolved.append((jt, _alias(jt), tables[jt], jkey, jr["role"]))
    return resolved


# ── Template dispatcher ───────────────────────────────────────────────────────

def _build_from_pattern(pattern, tables, insight=""):
    config = "{{ config(materialized='table') }}"
    if pattern is None:
        return _generic_fallback(tables, config)
    dispatch = {
        "revenue_analysis":  _revenue_analysis,
        "invoice_analysis":  _invoice_analysis,
        "product_analysis":  _product_analysis,
        "customer_analysis": _customer_analysis,
    }
    builder = dispatch.get(pattern["template"], _generic_fallback)
    return builder(pattern, tables, config, insight)


# ── Template: revenue_analysis ────────────────────────────────────────────────

def _revenue_analysis(rule, tables, config, insight=""):
    pt = _find_table(tables, *rule["primary"])
    if not pt:
        return _generic_fallback(tables, config)

    pa           = _alias(pt)
    pt_cols      = tables[pt]
    resolved     = _resolve_joins(rule["joins"], tables, pt_cols)
    insight_lower = insight.lower()

    metric_col = _find_col(pt_cols, *rule["metric_hints"])
    dim_col    = _find_col(pt_cols, *rule["dimension_hints"])
    order_id   = _find_col(pt_cols, "order_id") or "order_id"
    status_col = _find_col(pt_cols, "status")
    disc_col   = _find_col(pt_cols, "discount_pct", "discount")
    date_col   = _find_col(pt_cols, *rule["date_hints"])

    select_cols  = []
    join_clauses = []
    group_cols   = []
    used         = set()

    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{jkey} = {ja}.{jkey}"
        )
        if role == "dimension":
            for hint in ["city", "state", "segment", "region"]:
                c = _find_col(jcols, hint)
                if c and c not in used:
                    select_cols.append(f"{ja}.{c}")
                    group_cols.append(f"{ja}.{c}")
                    used.add(c)
            fn = _find_col(jcols, "first_name")
            ln = _find_col(jcols, "last_name")
            label = "customer_name" if "customer" in jt else "rep_name"
            if fn and ln and label not in used:
                expr = f"CONCAT({ja}.{fn}, ' ', {ja}.{ln})"
                select_cols.append(f"{expr} AS {label}")
                group_cols.append(expr)
                used.add(label)
            quota = _find_col(jcols, "quota")
            if quota and metric_col and "quota_inr" not in used:
                select_cols.append(f"MAX({ja}.{quota}) AS quota_inr")
                select_cols.append(
                    f"ROUND(100.0 * SUM({pa}.{metric_col}) "
                    f"/ NULLIF(MAX({ja}.{quota}), 0), 2) AS quota_attainment_pct"
                )
                used.add("quota_inr")
        elif role == "metric":
            qty  = _find_col(jcols, "quantity", "qty")
            line = _find_col(jcols, "line_total", "amount")
            if qty and "total_units_sold" not in used:
                select_cols.append(f"SUM({ja}.{qty}) AS total_units_sold")
                used.add("total_units_sold")
            if line and "total_line_revenue_inr" not in used:
                select_cols.append(f"SUM({ja}.{line}) AS total_line_revenue_inr")
                used.add("total_line_revenue_inr")

    # ── revenue_by_region / city — group by geography from customer join ──────
    if any(k in insight_lower for k in ["region", "city", "geographic", "location", "state", "area"]):
        geo_select  = []
        geo_group   = []
        geo_jns     = []
        found_geo   = False
        for jt, ja, jcols, jkey, role in resolved:
            geo_jns.append(f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{jkey} = {ja}.{jkey}")
            if role == "dimension" and "customer" in jt:
                cty = _find_col(jcols, "city")
                sta = _find_col(jcols, "state")
                seg = _find_col(jcols, "segment")
                if cty:
                    geo_select.append(f"{ja}.{cty}")
                    geo_group.append(f"{ja}.{cty}")
                    found_geo = True
                if sta:
                    geo_select.append(f"{ja}.{sta}")
                    geo_group.append(f"{ja}.{sta}")
                if seg:
                    geo_select.append(f"{ja}.{seg}")
                    geo_group.append(f"{ja}.{seg}")
            elif role == "metric":
                qty  = _find_col(jcols, "quantity", "qty")
                line = _find_col(jcols, "line_total")
                if qty and "total_units_sold" not in used:
                    geo_select.append(f"SUM({ja}.{qty}) AS total_units_sold")
                    used.add("total_units_sold")
                if line and "total_line_revenue_inr" not in used:
                    geo_select.append(f"SUM({ja}.{line}) AS total_line_revenue_inr")
                    used.add("total_line_revenue_inr")

        if found_geo:
            core = geo_select + [
                f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders",
                f"COUNT(DISTINCT {pa}.customer_id) AS unique_customers",
            ]
            if metric_col:
                core += [
                    f"SUM({pa}.{metric_col})   AS total_revenue_inr",
                    f"AVG({pa}.{metric_col})   AS avg_order_value_inr",
                ]
            if disc_col:
                core.append(f"AVG({pa}.{disc_col}) AS avg_discount_pct")
            if status_col:
                core.append(
                    f"SUM(CASE WHEN {pa}.{status_col} = \'Delivered\' "
                    f"THEN 1 ELSE 0 END) AS delivered_orders"
                )
            sel     = (",\n    ").join(core)
            grp_str = (",\n    ").join(geo_group) if geo_group else f"{pa}.{order_id}"
            jns_geo = "\n".join(geo_jns)
            order_b = "total_revenue_inr" if metric_col else "total_orders"
            return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns_geo}
GROUP BY
    {grp_str}
ORDER BY
    {order_b} DESC"""

    # ── monthly_revenue — group by month ──────────────────────────────────────
    if date_col and any(k in insight_lower for k in ["monthly", "daily", "trend", "over_time", "per_month"]):
        date_trunc = f"DATE_TRUNC('month', {pa}.{date_col})"
        core = [
            f"{date_trunc} AS revenue_month",
            f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders",
        ]
        if metric_col:
            core += [
                f"SUM({pa}.{metric_col})   AS total_revenue_inr",
                f"AVG({pa}.{metric_col})   AS avg_order_value_inr",
            ]
        if disc_col:
            core.append(f"AVG({pa}.{disc_col}) AS avg_discount_pct")
        all_sel = core + select_cols
        grp     = [date_trunc] + group_cols
        sel     = (",\n    ").join(all_sel)
        grp_str = (",\n    ").join(grp)
        jns     = "\n".join(join_clauses)
        return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
WHERE {pa}.{date_col} IS NOT NULL
GROUP BY
    {grp_str}
ORDER BY
    revenue_month ASC"""

    # ── rep_performance — focus on rep metrics ────────────────────────────────
    if any(k in insight_lower for k in ["rep", "quota", "performance"]):
        rep_id_col = _find_col(pt_cols, "rep_id") or "rep_id"
        if dim_col == rep_id_col or not dim_col:
            dim_col = rep_id_col
        core = [f"{pa}.{dim_col}"]
        if dim_col not in group_cols:
            group_cols.insert(0, f"{pa}.{dim_col}")

    # ── default revenue ───────────────────────────────────────────────────────
    if dim_col:
        group_cols.insert(0, f"{pa}.{dim_col}")

    core = []
    if dim_col:
        core.append(f"{pa}.{dim_col}")
    core.append(f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders")
    if metric_col:
        core += [
            f"SUM({pa}.{metric_col})   AS total_revenue_inr",
            f"AVG({pa}.{metric_col})   AS avg_order_value_inr",
        ]
    if disc_col:
        core.append(f"AVG({pa}.{disc_col}) AS avg_discount_pct")
    if status_col:
        core += [
            f"SUM(CASE WHEN {pa}.{status_col} = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders",
            f"SUM(CASE WHEN {pa}.{status_col} = 'Cancelled'  THEN 1 ELSE 0 END) AS cancelled_orders",
        ]

    all_sel  = core + select_cols
    order_by = "total_revenue_inr" if metric_col else "total_orders"
    grp      = group_cols if group_cols else ([f"{pa}.{dim_col}"] if dim_col else [f"{pa}.{order_id}"])

    # Deduplicate group_cols preserving order
    seen_grp = set()
    grp_dedup = []
    for g in grp:
        if g not in seen_grp:
            seen_grp.add(g)
            grp_dedup.append(g)

    sel     = (",\n    ").join(all_sel)
    grp_str = (",\n    ").join(grp_dedup)
    jns     = "\n".join(join_clauses)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp_str}
ORDER BY
    {order_by} DESC"""


# ── Template: invoice_analysis ────────────────────────────────────────────────

def _invoice_analysis(rule, tables, config, insight=""):
    pt = _find_table(tables, *rule["primary"])
    if not pt:
        return _generic_fallback(tables, config)

    pa      = _alias(pt)
    pt_cols = tables[pt]
    resolved = _resolve_joins(rule["joins"], tables, pt_cols)

    date_col   = _find_col(pt_cols, *rule["date_hints"])
    metric_col = _find_col(pt_cols, *rule["metric_hints"])
    flag_col   = _find_col(pt_cols, *rule.get("flag_hints", []))
    inv_id     = _find_col(pt_cols, "invoice_id") or "invoice_id"
    tax_col    = _find_col(pt_cols, "tax_amount", "tax_amount_inr")
    due_col    = _find_col(pt_cols, "due_date")
    insight_lower = insight.lower()

    join_clauses   = []
    customer_parts = []
    customer_group = []

    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{jkey} = {ja}.{jkey}"
        )
        if role == "dimension":
            fn  = _find_col(jcols, "first_name")
            ln  = _find_col(jcols, "last_name")
            em  = _find_col(jcols, "email")
            cty = _find_col(jcols, "city")
            seg = _find_col(jcols, "segment")
            if fn and ln:
                expr = f"CONCAT({ja}.{fn}, ' ', {ja}.{ln})"
                customer_parts.append(f"{expr} AS customer_name")
                customer_group.append(expr)
            if em:
                customer_parts.append(f"{ja}.{em}")
                customer_group.append(f"{ja}.{em}")
            if cty:
                customer_parts.append(f"{ja}.{cty}")
                customer_group.append(f"{ja}.{cty}")
            if seg:
                customer_parts.append(f"{ja}.{seg}")
                customer_group.append(f"{ja}.{seg}")

    jns          = "\n".join(join_clauses)
    date_trunc   = f"DATE_TRUNC('month', {pa}.{date_col})" if date_col else f"{pa}.{inv_id}"
    period_label = "invoice_month" if date_col else "invoice_id"

    # ── aging / overdue — bucket by days overdue ──────────────────────────────
    if any(k in insight_lower for k in ["aging", "overdue", "countdown", "due", "unpaid"]):
        aging_col = due_col or date_col
        if aging_col:
            return f"""{config}

SELECT
    CASE
        WHEN DATEDIFF('day', {pa}.{aging_col}, CURRENT_DATE()) <= 0  THEN 'Not yet due'
        WHEN DATEDIFF('day', {pa}.{aging_col}, CURRENT_DATE()) <= 30 THEN '1-30 days'
        WHEN DATEDIFF('day', {pa}.{aging_col}, CURRENT_DATE()) <= 60 THEN '31-60 days'
        WHEN DATEDIFF('day', {pa}.{aging_col}, CURRENT_DATE()) <= 90 THEN '61-90 days'
        ELSE '90+ days overdue'
    END                                         AS aging_bucket,
    COUNT({pa}.{inv_id})                        AS invoice_count,
    SUM({pa}.{metric_col})                      AS total_outstanding_inr,
    AVG({pa}.{metric_col})                      AS avg_invoice_value_inr
FROM {_ref(pt)} {pa}
{jns}
WHERE {pa}.{flag_col} = 0
GROUP BY 1
ORDER BY total_outstanding_inr DESC"""

    # ── collection_rate — paid vs unpaid by month ─────────────────────────────
    if any(k in insight_lower for k in ["collection", "paid", "payment"]):
        return f"""{config}

SELECT
    {date_trunc}                                AS invoice_month,
    COUNT({pa}.{inv_id})                        AS total_invoices,
    SUM(CASE WHEN {pa}.{flag_col} = 1
        THEN 1 ELSE 0 END)                      AS paid_count,
    SUM(CASE WHEN {pa}.{flag_col} = 0
        THEN 1 ELSE 0 END)                      AS unpaid_count,
    SUM({pa}.{metric_col})                      AS total_billed_inr,
    SUM(CASE WHEN {pa}.{flag_col} = 1
        THEN {pa}.{metric_col} ELSE 0 END)      AS collected_inr,
    ROUND(100.0 * SUM(CASE WHEN {pa}.{flag_col} = 1
        THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 2)               AS collection_rate_pct
FROM {_ref(pt)} {pa}
{jns}
WHERE {pa}.{date_col} IS NOT NULL
GROUP BY {date_trunc}
ORDER BY invoice_month ASC"""

    # ── default invoice — monthly summary ────────────────────────────────────
    select_parts = [
        f"{date_trunc} AS {period_label}",
        f"COUNT({pa}.{inv_id}) AS total_invoices",
    ]
    if metric_col:
        select_parts += [
            f"SUM({pa}.{metric_col})  AS total_billed_inr",
            f"AVG({pa}.{metric_col})  AS avg_invoice_value_inr",
        ]
    if tax_col:
        select_parts.append(f"SUM({pa}.{tax_col}) AS total_tax_collected_inr")
    if flag_col:
        select_parts += [
            f"SUM(CASE WHEN {pa}.{flag_col} = 1 THEN 1 ELSE 0 END) AS paid_invoices",
            f"SUM(CASE WHEN {pa}.{flag_col} = 0 THEN 1 ELSE 0 END) AS unpaid_invoices",
        ]
        if metric_col:
            select_parts.append(
                f"SUM(CASE WHEN {pa}.{flag_col} = 0 "
                f"THEN {pa}.{metric_col} ELSE 0 END) AS total_outstanding_inr"
            )
    if due_col and flag_col:
        select_parts.append(
            f"SUM(CASE WHEN {pa}.{flag_col} = 0 "
            f"AND DATEDIFF('day', {pa}.{due_col}, CURRENT_DATE()) > 0 "
            f"THEN 1 ELSE 0 END) AS overdue_invoices"
        )
    if metric_col:
        select_parts.append(
            f"RANK() OVER (ORDER BY SUM({pa}.{metric_col}) DESC) AS revenue_rank"
        )
    select_parts += customer_parts

    group_parts = [date_trunc] + customer_group
    where       = f"WHERE {pa}.{date_col} IS NOT NULL" if date_col else ""
    order_by    = "invoice_month ASC" if date_col else "total_billed_inr DESC"

    sel = (",\n    ").join(select_parts)
    grp = (",\n    ").join(group_parts)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
{where}
GROUP BY
    {grp}
ORDER BY
    {order_by}"""


# ── Template: product_analysis ────────────────────────────────────────────────

def _product_analysis(rule, tables, config, insight=""):
    pt = _find_table(tables, *rule["primary"])
    if not pt:
        return _generic_fallback(tables, config)

    pa      = _alias(pt)
    pt_cols = tables[pt]
    resolved = _resolve_joins(rule["joins"], tables, pt_cols)

    qty_col  = _find_col(pt_cols, *rule["metric_hints"])
    grp_col  = _find_col(pt_cols, *rule["dimension_hints"]) or pt_cols[0]
    order_id = _find_col(pt_cols, "order_id") or "order_id"
    line_col = _find_col(pt_cols, "line_total", "amount")
    disc_col = _find_col(pt_cols, "discount_pct", "discount")
    insight_lower = insight.lower()

    join_clauses  = []
    product_parts = []
    group_parts   = []

    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{jkey} = {ja}.{jkey}"
        )
        if role == "dimension":
            nm  = _find_col(jcols, "product_name", "name")
            cat = _find_col(jcols, "category")
            prc = _find_col(jcols, "unit_price", "price")
            cst = _find_col(jcols, "unit_cost", "cost")
            if nm:
                product_parts.append(f"{ja}.{nm}")
                group_parts.append(f"{ja}.{nm}")
            if cat:
                product_parts.append(f"{ja}.{cat}")
                group_parts.append(f"{ja}.{cat}")
            if prc:
                product_parts.append(f"{ja}.{prc} AS unit_price")
                group_parts.append(f"{ja}.{prc}")
            if prc and cst:
                product_parts.append(
                    f"ROUND(({ja}.{prc} - {ja}.{cst}) "
                    f"/ NULLIF({ja}.{prc}, 0) * 100, 2) AS margin_pct"
                )
                group_parts.append(f"{ja}.{cst}")
        elif role == "context":
            # Get date col from orders for monthly breakdown
            if any(k in insight_lower for k in ["monthly", "trend", "month"]):
                date_c = _find_col(jcols, "order_date", "date")
                if date_c:
                    join_clauses[-1]  # already added
                    # Store for use below
                    product_parts.insert(
                        0,
                        f"DATE_TRUNC('month', {ja}.{date_c}) AS sales_month"
                    )
                    group_parts.insert(0, f"DATE_TRUNC('month', {ja}.{date_c})")

    jns = "\n".join(join_clauses)

    # ── monthly_product_sales — group by month + product ─────────────────────
    if any(k in insight_lower for k in ["monthly", "month", "trend", "over_time"]):
        select_parts = (
            product_parts
            + [f"{pa}.{grp_col}"]
            + ([f"SUM({pa}.{qty_col}) AS total_qty_sold"] if qty_col else [])
            + ([f"SUM({pa}.{line_col}) AS total_revenue_inr"] if line_col else [])
            + [f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders"]
        )
        grp_all = group_parts + [f"{pa}.{grp_col}"]

        # Deduplicate
        seen = set()
        grp_dedup = []
        for g in grp_all:
            if g not in seen:
                seen.add(g)
                grp_dedup.append(g)

        order_by = "sales_month ASC" if "sales_month" in " ".join(product_parts) else "total_qty_sold DESC"

        sel = (",\n    ").join(select_parts)
        grp = (",\n    ").join(grp_dedup)
        return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp}
ORDER BY
    {order_by}"""

    # ── top_selling — rank by qty, limit 10 ──────────────────────────────────
    if any(k in insight_lower for k in ["top", "best", "most", "popular", "rank", "selling"]):
        select_parts = (
            product_parts
            + [f"{pa}.{grp_col}"]
            + ([f"SUM({pa}.{qty_col}) AS total_qty_sold"] if qty_col else [])
            + ([f"SUM({pa}.{line_col}) AS total_revenue_inr"] if line_col else [])
            + ([f"AVG({pa}.{disc_col}) AS avg_discount_pct"] if disc_col else [])
            + [f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders"]
            + ([f"RANK() OVER (ORDER BY SUM({pa}.{qty_col}) DESC) AS popularity_rank"] if qty_col else [])
        )
        grp_all = group_parts + [f"{pa}.{grp_col}"]
        seen = set()
        grp_dedup = []
        for g in grp_all:
            if g not in seen:
                seen.add(g)
                grp_dedup.append(g)

        sel = (",\n    ").join(select_parts)
        grp = (",\n    ").join(grp_dedup)
        return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp}
ORDER BY
    total_qty_sold DESC
LIMIT 10"""

    # ── default — category performance ───────────────────────────────────────
    select_parts = (
        product_parts
        + [f"{pa}.{grp_col}"]
        + ([f"SUM({pa}.{qty_col}) AS total_qty_sold"] if qty_col else [])
        + ([f"SUM({pa}.{line_col}) AS total_revenue_inr"] if line_col else [])
        + [f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders"]
    )
    grp_all = group_parts + [f"{pa}.{grp_col}"]
    seen = set()
    grp_dedup = []
    for g in grp_all:
        if g not in seen:
            seen.add(g)
            grp_dedup.append(g)

    sel = (",\n    ").join(select_parts)
    grp = (",\n    ").join(grp_dedup)
    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp}
ORDER BY
    total_qty_sold DESC"""


# ── Template: customer_analysis ───────────────────────────────────────────────

def _customer_analysis(rule, tables, config, insight=""):
    pt = _find_table(tables, *rule["primary"])
    if not pt:
        return _generic_fallback(tables, config)

    pa      = _alias(pt)
    pt_cols = tables[pt]
    resolved = _resolve_joins(rule["joins"], tables, pt_cols)

    cust_id  = _find_col(pt_cols, "customer_id") or "customer_id"
    date_col = _find_col(pt_cols, *rule["date_hints"]) if rule.get("date_hints") else None
    dim_col  = _find_col(pt_cols, *rule["dimension_hints"])
    flag_col = _find_col(pt_cols, *rule.get("flag_hints", []))
    insight_lower = insight.lower()

    join_clauses = []
    metric_parts = []
    used_aliases = set()

    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{cust_id} = {ja}.{jkey}"
        )
        if role == "metric":
            oid = _find_col(jcols, "order_id", "invoice_id") or "id"
            amt = _find_col(jcols, "total_amount", "total_inr", "amount")
            txn_alias = f"total_{jt.replace('stg_', '')}_count"
            if txn_alias not in used_aliases:
                metric_parts.append(f"COUNT(DISTINCT {ja}.{oid}) AS {txn_alias}")
                used_aliases.add(txn_alias)
            if amt:
                spend_alias = f"total_{jt.replace('stg_', '')}_spend_inr"
                if spend_alias not in used_aliases:
                    metric_parts += [
                        f"SUM({ja}.{amt})  AS {spend_alias}",
                        f"AVG({ja}.{amt})  AS avg_{jt.replace('stg_', '')}_value_inr",
                    ]
                    used_aliases.add(spend_alias)

    jns = "\n".join(join_clauses)

    # ── churn_rate — active vs churned by segment ─────────────────────────────
    if any(k in insight_lower for k in ["churn", "inactive", "lapse", "lost"]):
        seg_col = _find_col(pt_cols, "segment", "city", "state") or cust_id
        if not flag_col:
            return _generic_fallback(tables, config)
        return f"""{config}

SELECT
    {pa}.{seg_col},
    COUNT(DISTINCT {pa}.{cust_id})                  AS total_customers,
    SUM(CASE WHEN {pa}.{flag_col} = 1
        THEN 1 ELSE 0 END)                          AS active_customers,
    SUM(CASE WHEN {pa}.{flag_col} = 0
        THEN 1 ELSE 0 END)                          AS churned_customers,
    ROUND(100.0 * SUM(CASE WHEN {pa}.{flag_col} = 0
        THEN 1 ELSE 0 END)
        / NULLIF(COUNT(DISTINCT {pa}.{cust_id}), 0), 2) AS churn_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN {pa}.{flag_col} = 1
        THEN 1 ELSE 0 END)
        / NULLIF(COUNT(DISTINCT {pa}.{cust_id}), 0), 2) AS retention_rate_pct
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {pa}.{seg_col}
ORDER BY
    churn_rate_pct DESC"""

    # ── segment_breakdown — count + pct share per segment ────────────────────
    if any(k in insight_lower for k in ["segment", "breakdown", "distribution", "split"]):
        seg_col = _find_col(pt_cols, "segment") or dim_col or cust_id
        pct     = (f"ROUND(100.0 * COUNT(DISTINCT {pa}.{cust_id}) / "
                   f"SUM(COUNT(DISTINCT {pa}.{cust_id})) OVER (), 2) AS pct_share")
        active_lines = ""
        if flag_col:
            active_lines = (
                f",\n    SUM(CASE WHEN {pa}.{flag_col} = 1 THEN 1 ELSE 0 END) AS active_customers"
                f",\n    SUM(CASE WHEN {pa}.{flag_col} = 0 THEN 1 ELSE 0 END) AS inactive_customers"
            )
        metrics = (",\n    ").join(metric_parts)
        return f"""{config}

SELECT
    {pa}.{seg_col},
    COUNT(DISTINCT {pa}.{cust_id})          AS total_customers,
    {pct}{active_lines}{("," + chr(10) + "    ") if metrics else ""}
    {metrics}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {pa}.{seg_col}
ORDER BY
    total_customers DESC"""

    # ── total_active — filtered count by city/segment ────────────────────────
    if any(k in insight_lower for k in ["total_active", "active_count", "active_customer", "active"]):
        city_col = _find_col(pt_cols, "city", "state", "segment") or cust_id
        where    = f"WHERE {pa}.{flag_col} = 1" if flag_col else ""
        metrics  = (",\n    ").join(metric_parts) if metric_parts else ""
        return f"""{config}

SELECT
    {pa}.{city_col},
    COUNT(DISTINCT {pa}.{cust_id})          AS active_customers{("," + chr(10) + "    " + metrics) if metrics else ""}
FROM {_ref(pt)} {pa}
{jns}
{where}
GROUP BY
    {pa}.{city_col}
ORDER BY
    active_customers DESC"""

    # ── signup_trend — monthly new customers ─────────────────────────────────
    if any(k in insight_lower for k in ["signup", "trend", "new_customer", "acquisition", "monthly", "cohort"]):
        dc = date_col or _find_col(pt_cols, "signup_date", "created", "date")
        if dc:
            seg_col     = _find_col(pt_cols, "segment")
            seg_select  = f",\n    {pa}.{seg_col}" if seg_col else ""
            seg_group   = f",\n    {pa}.{seg_col}" if seg_col else ""
            active_line = ""
            if flag_col:
                active_line = (
                    f",\n    SUM(CASE WHEN {pa}.{flag_col} = 1 THEN 1 ELSE 0 END) AS active_signups"
                    f",\n    SUM(CASE WHEN {pa}.{flag_col} = 0 THEN 1 ELSE 0 END) AS churned_signups"
                )
            return f"""{config}

SELECT
    DATE_TRUNC('month', {pa}.{dc})          AS signup_month,
    COUNT(DISTINCT {pa}.{cust_id})          AS new_customers{seg_select}{active_line}
FROM {_ref(pt)} {pa}
{jns}
WHERE {pa}.{dc} IS NOT NULL
GROUP BY
    DATE_TRUNC('month', {pa}.{dc}){seg_group}
ORDER BY
    signup_month ASC"""

    # ── lifetime_value — total spend per customer ─────────────────────────────
    if any(k in insight_lower for k in ["lifetime", "ltv", "clv", "value"]):
        metrics = (",\n    ").join(metric_parts) if metric_parts else f"COUNT(DISTINCT {pa}.{cust_id}) AS total_count"
        return f"""{config}

SELECT
    {pa}.{cust_id},
    {metrics},
    RANK() OVER (ORDER BY {"total_orders_count" if metric_parts else "total_count"} DESC) AS value_rank
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {pa}.{cust_id}
ORDER BY
    {"total_orders_spend_inr" if "spend" in " ".join(metric_parts) else "total_orders_count"} DESC
LIMIT 100"""

    # ── default customer — group by best dimension ────────────────────────────
    group_expr  = f"{pa}.{dim_col}" if dim_col else f"{pa}.{cust_id}"
    pct         = (f"ROUND(100.0 * COUNT(DISTINCT {pa}.{cust_id}) / "
                   f"SUM(COUNT(DISTINCT {pa}.{cust_id})) OVER (), 2) AS pct_share")
    active_line = ""
    if flag_col:
        active_line = (
            f",\n    SUM(CASE WHEN {pa}.{flag_col} = 1 THEN 1 ELSE 0 END) AS active_customers"
            f",\n    SUM(CASE WHEN {pa}.{flag_col} = 0 THEN 1 ELSE 0 END) AS inactive_customers"
        )
    metrics = (",\n    ").join(metric_parts)
    return f"""{config}

SELECT
    {group_expr},
    COUNT(DISTINCT {pa}.{cust_id})          AS total_customers,
    {pct}{active_line}{("," + chr(10) + "    ") if metrics else ""}
    {metrics}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {group_expr}
ORDER BY
    total_customers DESC"""


# ── Generic fallback ──────────────────────────────────────────────────────────

def _generic_fallback(tables_or_rule, tables_or_config, config=None, insight=""):
    """Works with both (tables, config) and (rule, tables, config, insight) signatures."""
    if config is None:
        tables = tables_or_rule
        config = tables_or_config
    else:
        tables = tables_or_config

    if not tables:
        return f"{config}\n\nSELECT 1 AS placeholder"

    pt   = list(tables.keys())[0]
    cols = tables[pt]
    pa   = _alias(pt)
    gc   = _find_col(cols, "_id", "date", "status", "name") or cols[0]
    mc   = _find_col(cols, "_id") or cols[0]

    return f"""{config}

SELECT
    {gc},
    COUNT({mc}) AS total_count
FROM {_ref(pt)} {pa}
GROUP BY
    {gc}
ORDER BY
    total_count DESC"""