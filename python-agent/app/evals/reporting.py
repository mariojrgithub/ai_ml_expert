import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPORT_DIR = Path(__file__).parent / 'reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def build_report_artifacts(eval_run: Dict[str, Any]) -> Dict[str, str]:
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    json_path = REPORT_DIR / f'eval_report_{ts}.json'
    html_path = REPORT_DIR / f'eval_report_{ts}.html'
    json_path.write_text(json.dumps(eval_run, indent=2), encoding='utf-8')

    rows = []
    for r in eval_run.get('results', []):
        score = r.get('score', {})
        status = 'PASS' if score.get('passed') else 'FAIL'
        status_style = 'color:green;font-weight:bold' if score.get('passed') else 'color:red;font-weight:bold'
        failure = html.escape(str(score.get('failure_category', '')))
        row_id = html.escape(str(r.get('id', '')))
        task_type = html.escape(str(r.get('task_type', '')))
        rel = f"{score.get('relevance_score', 0.0):.2f}"
        gnd = f"{score.get('groundedness_score', 0.0):.2f}"
        abstain = '\u2713' if score.get('abstain') else ''
        rows.append(
            f"<tr>"
            f"<td>{row_id}</td>"
            f"<td>{task_type}</td>"
            f"<td style='{status_style}'>{status}</td>"
            f"<td>{failure}</td>"
            f"<td>{rel}</td>"
            f"<td>{gnd}</td>"
            f"<td style='text-align:center'>{abstain}</td>"
            f"<td>{html.escape(str(score.get('required_hits', [])))}</td>"
            f"<td>{html.escape(str(score.get('forbidden_hits', [])))}</td>"
            f"</tr>"
        )

    summary = eval_run.get('summary', {})
    summary_html = (
        f"Pass rate: <strong>{summary.get('pass_rate', 0.0):.1%}</strong> &nbsp;|&nbsp; "
        f"Passed: {summary.get('passed_cases', 0)} / {summary.get('total_cases', 0)} &nbsp;|&nbsp; "
        f"Avg relevance: {summary.get('avg_relevance_score', 0.0):.2f} &nbsp;|&nbsp; "
        f"Avg groundedness: {summary.get('avg_groundedness_score', 0.0):.2f} &nbsp;|&nbsp; "
        f"Abstained: {summary.get('abstain_count', 0)}"
    )

    report_html = f"""<html><head><title>Eval Report</title>
<style>
body{{font-family:Arial,sans-serif;padding:16px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:8px}}
th{{background:#f2f2f2}}
tr:nth-child(even){{background:#fafafa}}
</style></head><body>
<h1>Evaluation Report</h1>
<p>{summary_html}</p>
<table>
<tr><th>ID</th><th>Task</th><th>Status</th><th>Failure Category</th><th>Relevance</th><th>Groundedness</th><th>Abstain</th><th>Required Hits</th><th>Forbidden Hits</th></tr>
{''.join(rows)}
</table></body></html>"""
    html_path.write_text(report_html, encoding='utf-8')
    return {'json_report': str(json_path), 'html_report': str(html_path)}

def list_report_files() -> List[str]:
    return sorted(str(p) for p in REPORT_DIR.glob('*'))