from agent.llm import ask_llm
from agent.sql_to_dbt import convert_to_dbt
import re


def fix_sql(error, sql):
    short_error = error.strip().split("\n")[0][:300]

    # Remove the config block before sending — we'll add it back
    sql_body = re.sub(
        r"\{\{[^}]*config[^}]*\}\}", "", sql
    ).strip()

    prompt = f"""-- Fix this broken Snowflake dbt SQL.
-- Error: {short_error}
-- All table refs must use stg_ prefix: ref('stg_orders') not ref('orders')
-- Broken SQL:
{sql_body}
-- Fixed SQL (SELECT statement only, no config block):
SELECT"""

    response = ask_llm(prompt)

    # Strip any leading SELECT the LLM echoed back
    response = response.strip()
    if response.upper().startswith("SELECT"):
        response = response[6:].lstrip()

    # Rebuild with config + SELECT
    fixed = f"{{{{ config(materialized='table') }}}}\n\nSELECT\n{response}"

    # Enforce stg_ refs
    fixed = _enforce_stg_refs(fixed)

    # Final safety check
    if len(fixed.strip()) < 60:
        return sql

    return fixed


def _enforce_stg_refs(sql: str) -> str:
    def fix_ref(m):
        table = m.group(1)
        if not table.startswith("stg_"):
            table = f"stg_{table}"
        return f"{{{{ ref('{table}') }}}}"
    return re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", fix_ref, sql)

def _clean_healed_sql(response, original_sql):

    # Strip markdown fences
    response = response.replace("```sql", "").replace("```", "")

    # If the response has the config block already, use from there
    if "config(materialized" in response:
        # Find the config block start
        match = re.search(r"\{\{[\s\S]*?config\(materialized.*?\}\}", response)
        if match:
            response = response[match.start():]
    else:
        # Prepend config since we started with SELECT in the prompt
        response = "{{ config(materialized='table') }}\n\nSELECT" + response

    # Split on any line that looks like English prose
    # Keep lines that look like SQL, discard the rest
    lines = response.split("\n")
    sql_lines = []
    prose_streak = 0

    for line in lines:
        stripped = line.strip()

        # Always keep blank lines and config/jinja blocks
        if not stripped or stripped.startswith("{{") or stripped.startswith("{%"):
            sql_lines.append(line)
            prose_streak = 0
            continue

        # Detect prose: line starts with capital letter and has no SQL keywords
        is_sql = bool(re.search(
            r"^\s*(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|GROUP|ORDER|HAVING|WITH|ON|AND|OR|LIMIT|UNION|INSERT|UPDATE|--|\d+,?$)",
            stripped, re.IGNORECASE
        ))
        has_sql_chars = bool(re.search(r"[,\(\)\.\*=<>]", stripped))
        looks_like_prose = (
            stripped[0].isupper()
            and not is_sql
            and not has_sql_chars
            and len(stripped.split()) > 4
        )

        if looks_like_prose:
            prose_streak += 1
            # Once we hit 2 consecutive prose lines, stop — everything after is explanation
            if prose_streak >= 2:
                break
            continue

        prose_streak = 0
        sql_lines.append(line)

    cleaned = "\n".join(sql_lines).strip()

    # Final safety: if cleaned is too short or empty, fall back to original
    if len(cleaned) < 50:
        return original_sql

    return cleaned