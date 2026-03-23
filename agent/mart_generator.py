import re
from agent.llm import ask_llm


# ── Generic template routing rules ───────────────────────────────────────────
# 4 template types. Any LLM-generated insight routes to one via keyword scoring.
# No insight names are hardcoded — routing is purely keyword-based.

TEMPLATE_RULES = [
    {
        "keywords": ["revenue", "performance", "region", "rep", "sales",
                     "top", "rank", "best", "city", "geographic", "order",
                     "discount", "channel", "delivery", "fulfil"],
        "template": "revenue_analysis",
        "primary":  ["orders", "order"],
        "joins": [
            {"hints": ["customer"],        "key": "customer_id", "role": "dimension"},
            {"hints": ["sales_rep", "rep"], "key": "rep_id",      "role": "dimension"},
            {"hints": ["order_item", "item"], "key": "order_id",  "role": "metric"},
        ],
        "metric_hints":    ["total_amount", "total_inr", "amount", "line_total"],
        "dimension_hints": ["city", "state", "segment", "region", "rep_id",
                            "channel", "status", "payment_method"],
        "date_hints":      ["order_date", "created"],
    },
    {
        "keywords": ["invoice", "payment", "paid", "unpaid", "billing",
                     "tax", "overdue", "countdown", "aging", "gst",
                     "receivable", "due"],
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
                     "catalogue", "assortment"],
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
                     "cohort", "lifetime", "lapse"],
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
    """
    tables  = _parse_schema(schema_context)
    pattern = _match_pattern(insight)
    sql     = _build_from_pattern(pattern, tables)

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
    """Score each template rule against insight keywords. Return best match."""
    insight_lower = insight.lower()
    best, best_score = None, 0
    for rule in TEMPLATE_RULES:
        score = sum(1 for kw in rule["keywords"] if kw in insight_lower)
        if score > best_score:
            best_score = score
            best = rule
    return best


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
    return f"{{{{ ref('{table}') }}}}"


def _resolve_joins(join_rules, tables, primary_cols):
    """
    For each join rule, locate the actual table in the schema and verify
    the FK column exists in the primary table.
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


def _csv(items, indent=4):
    """Join a list into comma-separated lines with consistent indent."""
    pad = " " * indent
    if not items:
        return ""
    return (",\n" + pad).join(items)


# ── Template dispatcher ───────────────────────────────────────────────────────

def _build_from_pattern(pattern, tables):
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
    return builder(pattern, tables, config)


# ── Template: revenue_analysis ────────────────────────────────────────────────

def _revenue_analysis(rule, tables, config):
    pt = _find_table(tables, *rule["primary"])
    if not pt:
        return _generic_fallback(tables, config)

    pa      = _alias(pt)
    pt_cols = tables[pt]

    resolved = _resolve_joins(rule["joins"], tables, pt_cols)

    # Core columns
    metric_col = _find_col(pt_cols, *rule["metric_hints"])
    dim_col    = _find_col(pt_cols, *rule["dimension_hints"])
    order_id   = _find_col(pt_cols, "order_id") or "order_id"
    status_col = _find_col(pt_cols, "status")
    disc_col   = _find_col(pt_cols, "discount_pct", "discount")

    select_cols  = []
    join_clauses = []
    group_cols   = []

    # Track used aliases to prevent duplicates
    used_aliases = set()

    # Dimension columns from joined tables
    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{jkey} = {ja}.{jkey}"
        )
        if role == "dimension":
            for hint in ["city", "state", "segment", "region"]:
                c = _find_col(jcols, hint)
                if c and c not in used_aliases:
                    select_cols.append(f"{ja}.{c}")
                    group_cols.append(f"{ja}.{c}")
                    used_aliases.add(c)
            # Rep/person name — only add once
            fn = _find_col(jcols, "first_name")
            ln = _find_col(jcols, "last_name")
            name_alias = f"{ja}_name"
            if fn and ln and name_alias not in used_aliases:
                # Use table-prefixed alias so customer vs rep names don't clash
                label = "customer_name" if "customer" in jt else "rep_name"
                if label not in used_aliases:
                    expr = f"CONCAT({ja}.{fn}, ' ', {ja}.{ln})"
                    select_cols.append(f"{expr} AS {label}")
                    group_cols.append(expr)
                    used_aliases.add(label)
            # Quota attainment
            quota = _find_col(jcols, "quota")
            if quota and metric_col and "quota_inr" not in used_aliases:
                select_cols.append(f"MAX({ja}.{quota}) AS quota_inr")
                select_cols.append(
                    f"ROUND(100.0 * SUM({pa}.{metric_col}) / NULLIF(MAX({ja}.{quota}), 0), 2) "
                    f"AS quota_attainment_pct"
                )
                used_aliases.add("quota_inr")

        elif role == "metric":
            qty  = _find_col(jcols, "quantity", "qty")
            line = _find_col(jcols, "line_total", "amount")
            if qty and "total_units_sold" not in used_aliases:
                select_cols.append(f"SUM({ja}.{qty}) AS total_units_sold")
                used_aliases.add("total_units_sold")
            if line and "total_line_revenue_inr" not in used_aliases:
                select_cols.append(f"SUM({ja}.{line}) AS total_line_revenue_inr")
                used_aliases.add("total_line_revenue_inr")

    # Primary table group dimension
    if dim_col:
        group_cols.insert(0, f"{pa}.{dim_col}")

    # Core aggregates
    core = []
    if dim_col:
        core.append(f"{pa}.{dim_col}")
    core.append(f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders")
    if metric_col:
        core.append(f"SUM({pa}.{metric_col})       AS total_revenue_inr")
        core.append(f"AVG({pa}.{metric_col})       AS avg_order_value_inr")
    if disc_col:
        core.append(f"AVG({pa}.{disc_col})         AS avg_discount_pct")
    if status_col:
        core.append(
            f"SUM(CASE WHEN {pa}.{status_col} = 'Delivered' "
            f"THEN 1 ELSE 0 END) AS delivered_orders"
        )
        core.append(
            f"SUM(CASE WHEN {pa}.{status_col} = 'Cancelled' "
            f"THEN 1 ELSE 0 END) AS cancelled_orders"
        )

    all_select = core + select_cols
    order_by   = "total_revenue_inr" if metric_col else "total_orders"
    group_by   = group_cols if group_cols else ([f"{pa}.{dim_col}"] if dim_col else [f"{pa}.{order_id}"])

    sel  = (",\n    ").join(all_select)
    grp  = (",\n    ").join(group_by)
    jns  = "\n".join(join_clauses)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp}
ORDER BY
    {order_by} DESC"""


# ── Template: invoice_analysis ────────────────────────────────────────────────

def _invoice_analysis(rule, tables, config):
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

    date_trunc = f"DATE_TRUNC('month', {pa}.{date_col})" if date_col else f"{pa}.{inv_id}"
    period_label = "invoice_month" if date_col else "invoice_id"

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
                f"SUM(CASE WHEN {pa}.{flag_col} = 0 THEN {pa}.{metric_col} ELSE 0 END) "
                f"AS total_outstanding_inr"
            )
    if due_col:
        select_parts.append(
            f"SUM(CASE WHEN {pa}.{flag_col} = 0 "
            f"AND DATEDIFF('day', {pa}.{due_col}, CURRENT_DATE()) > 0 "
            f"THEN 1 ELSE 0 END) AS overdue_invoices"
            if flag_col else
            f"MAX(DATEDIFF('day', {pa}.{due_col}, CURRENT_DATE())) AS max_days_overdue"
        )
    select_parts += customer_parts
    if metric_col:
        select_parts.append(
            f"RANK() OVER (ORDER BY SUM({pa}.{metric_col}) DESC) AS revenue_rank"
        )

    group_parts = [date_trunc] + customer_group
    where_clause = f"WHERE {pa}.{date_col} IS NOT NULL" if date_col else ""
    order_by     = "invoice_month ASC" if date_col else "total_billed_inr DESC"

    sel = (",\n    ").join(select_parts)
    grp = (",\n    ").join(group_parts)
    jns = "\n".join(join_clauses)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
{where_clause}
GROUP BY
    {grp}
ORDER BY
    {order_by}"""


# ── Template: product_analysis ────────────────────────────────────────────────

def _product_analysis(rule, tables, config):
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
                    f"ROUND(({ja}.{prc} - {ja}.{cst}) / NULLIF({ja}.{prc}, 0) * 100, 2) "
                    f"AS margin_pct"
                )
                group_parts.append(f"{ja}.{cst}")

    select_parts = product_parts + [f"{pa}.{grp_col}"]
    if qty_col:
        select_parts.append(f"SUM({pa}.{qty_col}) AS total_qty_sold")
    if line_col:
        select_parts.append(f"SUM({pa}.{line_col}) AS total_revenue_inr")
    if disc_col:
        select_parts.append(f"AVG({pa}.{disc_col}) AS avg_discount_pct")
    select_parts.append(
        f"COUNT(DISTINCT {pa}.{order_id}) AS total_orders"
    )
    if qty_col:
        select_parts.append(
            f"RANK() OVER (ORDER BY SUM({pa}.{qty_col}) DESC) AS popularity_rank"
        )

    group_parts.append(f"{pa}.{grp_col}")
    order_by = f"total_qty_sold DESC" if qty_col else "total_orders DESC"

    sel = (",\n    ").join(select_parts)
    grp = (",\n    ").join(group_parts)
    jns = "\n".join(join_clauses)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
GROUP BY
    {grp}
ORDER BY
    {order_by}
LIMIT 10"""


# ── Template: customer_analysis ───────────────────────────────────────────────

def _customer_analysis(rule, tables, config):
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

    join_clauses  = []
    metric_parts  = []
    used_metric_aliases = set()

    for jt, ja, jcols, jkey, role in resolved:
        join_clauses.append(
            f"LEFT JOIN {_ref(jt)} {ja}\n    ON {pa}.{cust_id} = {ja}.{jkey}"
        )
        if role == "metric":
            oid = _find_col(jcols, "order_id", "invoice_id") or "id"
            amt = _find_col(jcols, "total_amount", "total_inr", "amount")
            # Use table-specific aliases to avoid duplicates across joins
            txn_alias = f"total_{jt.replace('stg_', '')}_count"
            if txn_alias not in used_metric_aliases:
                metric_parts.append(
                    f"COUNT(DISTINCT {ja}.{oid}) AS {txn_alias}"
                )
                used_metric_aliases.add(txn_alias)
            if amt:
                spend_alias = f"total_{jt.replace('stg_', '')}_spend_inr"
                avg_alias   = f"avg_{jt.replace('stg_', '')}_value_inr"
                if spend_alias not in used_metric_aliases:
                    metric_parts += [
                        f"SUM({ja}.{amt})    AS {spend_alias}",
                        f"AVG({ja}.{amt})    AS {avg_alias}",
                    ]
                    used_metric_aliases.add(spend_alias)

    # Group / period expression
    if date_col:
        group_expr   = f"DATE_TRUNC('month', {pa}.{date_col})"
        period_label = "signup_month"
        where        = f"WHERE {pa}.{date_col} IS NOT NULL"
        order_by     = "signup_month ASC"
    elif dim_col:
        group_expr   = f"{pa}.{dim_col}"
        period_label = dim_col
        where        = ""
        order_by     = "total_customers DESC"
    else:
        group_expr   = f"{pa}.{cust_id}"
        period_label = "customer_id"
        where        = ""
        order_by     = "total_customers DESC"

    select_parts = [
        f"{group_expr} AS {period_label}",
        f"COUNT(DISTINCT {pa}.{cust_id}) AS total_customers",
        f"ROUND(100.0 * COUNT(DISTINCT {pa}.{cust_id}) / "
        f"SUM(COUNT(DISTINCT {pa}.{cust_id})) OVER (), 2) AS pct_share",
    ]
    if flag_col:
        select_parts += [
            f"SUM(CASE WHEN {pa}.{flag_col} = 1 THEN 1 ELSE 0 END) AS active_customers",
            f"SUM(CASE WHEN {pa}.{flag_col} = 0 THEN 1 ELSE 0 END) AS inactive_customers",
        ]
    select_parts += metric_parts
    select_parts.append(
        f"RANK() OVER (ORDER BY COUNT(DISTINCT {pa}.{cust_id}) DESC) AS segment_rank"
    )

    sel = (",\n    ").join(select_parts)
    jns = "\n".join(join_clauses)

    return f"""{config}

SELECT
    {sel}
FROM {_ref(pt)} {pa}
{jns}
{where}
GROUP BY
    {group_expr}
ORDER BY
    {order_by}"""


# ── Generic fallback ──────────────────────────────────────────────────────────

def _generic_fallback(tables_or_rule, tables_or_config, config=None):
    """
    Called when no pattern matches or a template cannot find its primary table.
    Accepts both (tables, config) and (rule, tables, config) signatures.
    """
    if config is None:
        # Called as (tables, config)
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