"""Tests for eval runner score_case — no LLM or DB required.

Docker-only packages are stubbed by conftest.py.
"""
import sys
from unittest.mock import MagicMock

from app.evals.runner import score_case, load_dataset  # noqa: E402


# ---------------------------------------------------------------------------
# score_case
# ---------------------------------------------------------------------------

def _make_meta(**kwargs):
    defaults = {"grounded": False, "abstain": False, "relevance_score": 0.5, "groundedness_score": 0.6}
    defaults.update(kwargs)
    return defaults


def test_score_case_passes_when_all_required_present():
    case = {"required_keywords": ["def", "json"], "forbidden_keywords": []}
    result = score_case("def parse_json(data): return json.loads(data)", [], case, _make_meta())
    assert result["passed"] is True
    assert result["failure_category"] == "none"


def test_score_case_fails_on_missing_required_keyword():
    case = {"required_keywords": ["def", "json"], "forbidden_keywords": []}
    result = score_case("parse the data", [], case, _make_meta())
    assert result["passed"] is False
    assert result["failure_category"] == "missing_required"


def test_score_case_fails_on_forbidden_keyword():
    case = {"required_keywords": ["select"], "forbidden_keywords": ["drop"]}
    result = score_case("select * from t; drop table t", [], case, _make_meta())
    assert result["passed"] is False
    assert result["failure_category"] == "forbidden_present"


def test_score_case_fails_when_grounding_required_but_missing():
    case = {"required_keywords": [], "forbidden_keywords": [], "requires_grounding": True}
    result = score_case("some answer", [], case, _make_meta(grounded=False))
    assert result["passed"] is False
    assert result["failure_category"] == "grounding_missing"


def test_score_case_passes_when_grounding_required_and_present():
    case = {"required_keywords": [], "forbidden_keywords": [], "requires_grounding": True}
    result = score_case("some answer", [], case, _make_meta(grounded=True))
    assert result["passed"] is True


def test_score_case_fails_when_abstain_expected_but_not_abstained():
    case = {"required_keywords": [], "forbidden_keywords": [], "expected_abstain": True}
    result = score_case("I found the answer", [], case, _make_meta(abstain=False))
    assert result["passed"] is False
    assert result["failure_category"] == "abstain_mismatch"


def test_score_case_passes_when_abstain_expected_and_abstained():
    case = {"required_keywords": [], "forbidden_keywords": [], "expected_abstain": True}
    result = score_case("I cannot answer this", [], case, _make_meta(abstain=True))
    assert result["passed"] is True


def test_score_case_includes_checker_scores_in_result():
    case = {"required_keywords": [], "forbidden_keywords": []}
    result = score_case("answer", [], case, _make_meta(relevance_score=0.42, groundedness_score=0.77))
    assert result["relevance_score"] == 0.42
    assert result["groundedness_score"] == 0.77


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------

def test_load_dataset_returns_15_cases():
    cases = load_dataset()
    assert len(cases) == 15


def test_load_dataset_all_have_id_and_input():
    for case in load_dataset():
        assert "id" in case
        assert "input" in case


def test_load_dataset_abstain_case_exists():
    cases = load_dataset()
    abstain_cases = [c for c in cases if c.get("expected_abstain")]
    assert len(abstain_cases) >= 1
