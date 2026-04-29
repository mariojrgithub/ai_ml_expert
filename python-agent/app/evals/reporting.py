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
        failure = html.escape(str(score.get('failure_category', '')))
        row_id = html.escape(str(r.get('id', '')))
        task_type = html.escape(str(r.get('task_type', '')))
        rows.append(
            f"<tr><td>{row_id}</td><td>{task_type}</td>"
            f"<td>{status}</td><td>{failure}</td>"
            f"<td>{html.escape(str(score.get('required_hits', [])))}</td>"
            f"<td>{html.escape(str(score.get('forbidden_hits', [])))}</td></tr>"
        )

    report_html = f"""<html><head><title>Eval Report</title>
<style>
body{{font-family:Arial,sans-serif}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:8px}}
</style></head><body>
<h1>Evaluation Report</h1>
<p>Summary: {eval_run.get('summary')}</p>
<table>
<tr><th>ID</th><th>Task</th><th>Status</th><th>Failure Category</th><th>Required Hits</th><th>Forbidden Hits</th></tr>
{''.join(rows)}
</table></body></html>"""
    html_path.write_text(report_html, encoding='utf-8')
    return {'json_report': str(json_path), 'html_report': str(html_path)}

def list_report_files() -> List[str]:
    return sorted(str(p) for p in REPORT_DIR.glob('*'))