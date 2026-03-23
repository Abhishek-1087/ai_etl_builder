import json
import os
from datetime import datetime
import decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


REPORT_PATH = "pipeline_report.json"
HTML_REPORT_PATH = "pipeline_dashboard.html"


def build_report(schema, drift, scored_profiles, dbt_success, run_log, mart_models):
    """
    Assemble a full delivery health report dict.
    """

    overall_trust = 0
    if scored_profiles:
        overall_trust = round(
            sum(p["trust_score"] for p in scored_profiles) / len(scored_profiles), 1
        )

    report = {
        "run_at": datetime.utcnow().isoformat() + "Z",
        "pipeline_status": "SUCCESS" if dbt_success else "FAILED",
        "overall_trust_score": overall_trust,
        "tables_profiled": len(scored_profiles),
        "mart_models_generated": len(mart_models),
        "schema_drift": drift,
        "data_quality": scored_profiles,
        "mart_models": [m["name"] for m in mart_models],
    }

    return report


def save_json_report(report):
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2, cls=DecimalEncoder)
    print(f"JSON report saved: {REPORT_PATH}")


def _trust_color(score):
    if score >= 80:
        return "#22c55e"   # green
    elif score >= 50:
        return "#f59e0b"   # amber
    return "#ef4444"       # red


def _status_color(status):
    return "#22c55e" if status == "SUCCESS" else "#ef4444"


def save_html_dashboard(report):
    """
    Generate a self-contained HTML dashboard.
    """

    tables_html = ""
    for p in report["data_quality"]:
        score = p["trust_score"]
        color = _trust_color(score)
        warnings_html = ""
        if p["warnings"]:
            items = "".join(f"<li>{w}</li>" for w in p["warnings"])
            warnings_html = f'<ul class="warnings">{items}</ul>'

        cols_html = ""
        for col_name, stats in p.get("columns", {}).items():
            null_pct = stats.get("null_pct", "n/a")
            null_pct_display = f"{null_pct}%" if null_pct is not None else "n/a"
            flag = " ⚠" if (null_pct is not None and null_pct > 20) else ""
            cols_html += f"""
            <tr>
              <td>{col_name}</td>
              <td>{stats.get('type','')}</td>
              <td class="{'warn' if flag else ''}">{null_pct_display}{flag}</td>
              <td>{stats.get('distinct_count', 'n/a')}</td>
            </tr>"""

        tables_html += f"""
        <div class="table-card">
          <div class="table-header">
            <span class="table-name">{p['table']}</span>
            <span class="trust-badge" style="background:{color}">{score}/100</span>
          </div>
          <div class="meta">Rows: {p['row_count']:,} &nbsp;|&nbsp; Avg null rate: {p['avg_null_pct']}%</div>
          {warnings_html}
          <details>
            <summary>Column details</summary>
            <table class="col-table">
              <thead><tr><th>Column</th><th>Type</th><th>Null %</th><th>Distinct</th></tr></thead>
              <tbody>{cols_html}</tbody>
            </table>
          </details>
        </div>"""

    drift = report["schema_drift"]
    drift_html = "<p>No schema drift detected.</p>"
    if drift.get("has_drift"):
        parts = []
        if drift["new_tables"]:
            parts.append("<b>New tables:</b> " + ", ".join(drift["new_tables"]))
        if drift["removed_tables"]:
            parts.append("<b>Removed tables:</b> " + ", ".join(drift["removed_tables"]))
        if drift["changed_tables"]:
            for t, ch in drift["changed_tables"].items():
                added = ", ".join(ch["columns_added"]) or "none"
                removed = ", ".join(ch["columns_removed"]) or "none"
                parts.append(f"<b>{t}</b>: +[{added}] -[{removed}]")
        drift_html = "<ul>" + "".join(f"<li>{p}</li>" for p in parts) + "</ul>"

    marts_html = "".join(
        f'<span class="mart-pill">{m}</span>' for m in report["mart_models"]
    )

    status = report["pipeline_status"]
    status_color = _status_color(status)
    overall_trust = report["overall_trust_score"]
    trust_color = _trust_color(overall_trust)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI ETL Pipeline Dashboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; padding: 32px; }}
  h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 13px; margin-bottom: 32px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 20px; }}
  .card-label {{ font-size: 12px; color: #64748b; text-transform: uppercase; letter-spacing: .05em; }}
  .card-value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 15px; font-weight: 600; color: #94a3b8;
                 text-transform: uppercase; letter-spacing: .06em; margin-bottom: 14px; }}
  .table-card {{ background: #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 12px; }}
  .table-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
  .table-name {{ font-weight: 600; font-size: 15px; }}
  .trust-badge {{ color: #fff; font-size: 13px; font-weight: 700;
                  padding: 3px 10px; border-radius: 20px; }}
  .meta {{ font-size: 12px; color: #64748b; margin-bottom: 8px; }}
  .warnings {{ font-size: 12px; color: #f59e0b; padding-left: 16px; margin-bottom: 8px; }}
  details summary {{ font-size: 12px; color: #64748b; cursor: pointer; margin-top: 8px; }}
  .col-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
  .col-table th {{ text-align: left; color: #64748b; padding: 4px 8px; border-bottom: 1px solid #334155; }}
  .col-table td {{ padding: 4px 8px; border-bottom: 1px solid #1e293b; }}
  .warn {{ color: #f59e0b; }}
  .drift-box {{ background: #1e293b; border-radius: 10px; padding: 18px; font-size: 14px; line-height: 1.8; }}
  .mart-pill {{ background: #1e3a5f; color: #93c5fd; font-size: 12px;
                padding: 4px 10px; border-radius: 20px; margin-right: 8px;
                display: inline-block; margin-bottom: 6px; }}
</style>
</head>
<body>
<h1>AI ETL Pipeline Dashboard</h1>
<p class="subtitle">Run at {report['run_at']}</p>

<div class="cards">
  <div class="card">
    <div class="card-label">Pipeline status</div>
    <div class="card-value" style="color:{status_color}">{status}</div>
  </div>
  <div class="card">
    <div class="card-label">Overall trust score</div>
    <div class="card-value" style="color:{trust_color}">{overall_trust}/100</div>
  </div>
  <div class="card">
    <div class="card-label">Tables profiled</div>
    <div class="card-value">{report['tables_profiled']}</div>
  </div>
  <div class="card">
    <div class="card-label">Mart models</div>
    <div class="card-value">{report['mart_models_generated']}</div>
  </div>
</div>

<div class="section">
  <h2>Data Quality by Table</h2>
  {tables_html if tables_html else '<p style="color:#64748b">No profiling data available.</p>'}
</div>

<div class="section">
  <h2>Schema Drift</h2>
  <div class="drift-box">{drift_html}</div>
</div>

<div class="section">
  <h2>Generated Mart Models</h2>
  <div>{marts_html if marts_html else '<span style="color:#64748b">None</span>'}</div>
</div>

</body>
</html>"""

    with open(HTML_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML dashboard saved: {HTML_REPORT_PATH}")


def generate_and_save(schema, drift, scored_profiles, dbt_success, run_log, mart_models):
    report = build_report(schema, drift, scored_profiles, dbt_success, run_log, mart_models)
    save_json_report(report)
    save_html_dashboard(report)
    return report
