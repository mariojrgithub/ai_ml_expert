"""Tests for app.checker — all three quality-check functions."""
from app.checker import check_relevance, check_groundedness, check_citation_sufficiency


# ---------------------------------------------------------------------------
# A — Relevance check
# ---------------------------------------------------------------------------

def test_relevance_passes_for_on_topic_answer():
    score, passed = check_relevance(
        "What is the CI/CD pipeline strategy?",
        "The CI/CD pipeline strategy involves unit tests, integration tests, "
        "and deployment stages separated by quality gates.",
    )
    assert passed is True
    assert score > 0.0


def test_relevance_fails_for_empty_answer():
    score, passed = check_relevance("What is Docker?", "")
    assert passed is False
    assert score == 0.0


def test_relevance_fails_for_completely_off_topic_answer():
    score, passed = check_relevance(
        "Explain Kubernetes pod scheduling",
        "The quick brown fox jumped over the lazy dog.",
    )
    assert passed is False


def test_relevance_returns_float_between_0_and_1():
    score, _ = check_relevance("some question", "some answer about question")
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# B — Groundedness check
# ---------------------------------------------------------------------------

def test_groundedness_skips_non_qa_intents():
    score, ungrounded = check_groundedness("SELECT * FROM x", [], [], "SQL")
    assert score == 1.0
    assert ungrounded == []


def test_groundedness_zero_when_no_evidence():
    score, ungrounded = check_groundedness(
        "The answer is that Python uses indentation for blocks.",
        [], [], "QA"
    )
    assert score == 0.0


def test_groundedness_high_when_answer_traceable_to_doc():
    docs = [{"text": "Python uses indentation to define code blocks and scopes."}]
    score, ungrounded = check_groundedness(
        "Python uses indentation for blocks and scopes in code.",
        docs, [], "QA"
    )
    assert score > 0.0


def test_groundedness_returns_ungrounded_sentences_when_low():
    docs = [{"text": "CI/CD pipelines run unit tests before deployment."}]
    # Sentence has no overlap with the doc
    score, ungrounded = check_groundedness(
        "The capital of France is Paris. Rivers flow downhill always.",
        docs, [], "QA"
    )
    assert len(ungrounded) > 0


# ---------------------------------------------------------------------------
# C — Citation sufficiency check
# ---------------------------------------------------------------------------

def test_citation_check_warns_when_grounded_qa_has_no_citations():
    warnings = check_citation_sufficiency("QA", grounded=True, citations=[])
    assert len(warnings) == 1
    assert "citation" in warnings[0].lower()


def test_citation_check_no_warning_when_citations_present():
    warnings = check_citation_sufficiency(
        "QA", grounded=True, citations=[{"source": "s", "title": "t", "snippet": "x"}]
    )
    assert warnings == []


def test_citation_check_no_warning_for_code_intent():
    warnings = check_citation_sufficiency("CODE", grounded=False, citations=[])
    assert warnings == []


def test_citation_check_no_warning_for_ungrounded_qa():
    warnings = check_citation_sufficiency("QA", grounded=False, citations=[])
    assert warnings == []
