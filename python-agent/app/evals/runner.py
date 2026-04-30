import json
from pathlib import Path
from typing import Any, Dict, List
from ..agent_runtime import run_agent_with_trace
from ..store import save_eval_run
from .reporting import build_report_artifacts
DEFAULT_DATASET_PATH = Path(__file__).parent / 'datasets' / 'golden_eval_set.json'

def load_dataset(path: Path | None = None) -> List[Dict[str, Any]]:
    return json.loads((path or DEFAULT_DATASET_PATH).read_text(encoding='utf-8'))

def score_case(output: str, warnings: List[str], case: Dict[str, Any], run_metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    meta = run_metadata or {}
    normalized = output.lower(); required = case.get('required_keywords', []); forbidden = case.get('forbidden_keywords', [])
    required_hits = [kw for kw in required if kw.lower() in normalized]
    forbidden_hits = [kw for kw in forbidden if kw.lower() in normalized]
    grounded_required = case.get('requires_grounding', False)
    grounded_ok = True if not grounded_required else bool(meta.get('grounded', False))
    # abstain expectation: if the case expects abstain, the agent must have abstained
    expected_abstain = case.get('expected_abstain', False)
    abstain_ok = (meta.get('abstain', False) == expected_abstain)
    passed = len(required_hits) == len(required) and len(forbidden_hits) == 0 and grounded_ok and abstain_ok
    failure_category = 'none'
    if not abstain_ok:
        failure_category = 'abstain_mismatch'
    elif len(forbidden_hits) > 0:
        failure_category = 'forbidden_present'
    elif len(required_hits) != len(required):
        failure_category = 'missing_required'
    elif not grounded_ok:
        failure_category = 'grounding_missing'
    elif len(warnings) >= 3:
        failure_category = 'warning_heavy'
    return {
        'passed': passed,
        'required_keywords': required, 'required_hits': required_hits,
        'forbidden_keywords': forbidden, 'forbidden_hits': forbidden_hits,
        'warning_count': len(warnings),
        'failure_category': failure_category,
        'relevance_score': float(meta.get('relevance_score', 0.0)),
        'groundedness_score': float(meta.get('groundedness_score', 0.0)),
        'abstain': bool(meta.get('abstain', False)),
    }

def run_eval_case(case: Dict[str, Any]) -> Dict[str, Any]:
    result = run_agent_with_trace(session_id=f"eval-{case['id']}", user_input=case['input'])
    answer = result.get('validated_output', ''); warnings = result.get('warnings', []); metadata = result.get('run_metadata', {})
    return {'id': case['id'], 'task_type': case.get('task_type'), 'input': case['input'], 'answer': answer, 'warnings': warnings, 'trace': result.get('trace', []), 'run_metadata': metadata, 'score': score_case(answer, warnings, case, metadata)}

def run_all_evals() -> Dict[str, Any]:
    cases = load_dataset(); results = [run_eval_case(case) for case in cases]
    passed = sum(1 for r in results if r['score']['passed']); total = len(results)
    failure_counts = {}
    for r in results:
        fc = r['score'].get('failure_category', 'none'); failure_counts[fc] = failure_counts.get(fc, 0) + 1
    avg_relevance = round(sum(r['score'].get('relevance_score', 0.0) for r in results) / total, 4) if total else 0.0
    avg_groundedness = round(sum(r['score'].get('groundedness_score', 0.0) for r in results) / total, 4) if total else 0.0
    abstain_count = sum(1 for r in results if r['score'].get('abstain', False))
    eval_run = {'summary': {'total_cases': total, 'passed_cases': passed, 'failed_cases': total - passed, 'pass_rate': round((passed / total) if total else 0.0, 4), 'failure_counts': failure_counts, 'avg_relevance_score': avg_relevance, 'avg_groundedness_score': avg_groundedness, 'abstain_count': abstain_count}, 'results': results, 'dataset': 'golden_eval_set.json'}
    eval_run['reports'] = build_report_artifacts(eval_run)
    eval_run_id = save_eval_run(eval_run); eval_run['eval_run_id'] = eval_run_id
    return eval_run