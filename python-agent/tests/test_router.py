from app.router import classify_intent, plan_context
from app.config import settings


def test_classify_python_code():
    result = classify_intent("Write code for a JSON parser in Python")
    assert result["intent"] == "CODE"
    assert result["domain"] == "python"


def test_classify_python_factual_question_is_qa():
    result = classify_intent("What is the latest Python release?")
    assert result["intent"] == "QA"
    assert result["domain"] == "python"


def test_plan_context_marks_freshness():
    original = settings.web_search_enabled
    settings.web_search_enabled = True
    try:
        result = plan_context("What are the latest CI/CD recommendations?", "QA")
        assert result["needs_web_search"] is True
    finally:
        settings.web_search_enabled = original


# ---------------------------------------------------------------------------
# Confidence scores
# ---------------------------------------------------------------------------

def test_mongo_explicit_syntax_has_high_confidence():
    result = classify_intent("db.collection.aggregate([{ $match: {} }])")
    assert result["intent"] == "MONGO"
    assert result["confidence"] >= 0.90


def test_sql_select_has_high_confidence():
    result = classify_intent("SELECT * FROM users WHERE id = 1")
    assert result["intent"] == "SQL"
    assert result["confidence"] >= 0.90


def test_code_explicit_marker_has_high_confidence():
    result = classify_intent("Write code for a bubble sort in Python")
    assert result["intent"] == "CODE"
    assert result["confidence"] >= 0.85


def test_qa_with_known_domain_has_medium_high_confidence():
    result = classify_intent("How does backpropagation work in neural networks?")
    assert result["intent"] == "QA"
    assert result["confidence"] >= 0.75


def test_qa_generic_has_lower_confidence():
    result = classify_intent("What is the meaning of life?")
    assert result["intent"] == "QA"
    assert result["domain"] == "general"
    assert result["confidence"] < 0.75


# ---------------------------------------------------------------------------
# Ambiguity flag
# ---------------------------------------------------------------------------

def test_ambiguity_flag_set_for_low_confidence():
    result = classify_intent("What is the meaning of life?")
    assert result["ambiguity_flag"] is True


def test_ambiguity_flag_not_set_for_high_confidence():
    result = classify_intent("SELECT count(*) FROM sessions")
    assert result["ambiguity_flag"] is False


def test_result_always_contains_ambiguity_flag():
    for msg in [
        "implement a red-black tree",
        "db.orders.find({})",
        "what is a neural network?",
    ]:
        result = classify_intent(msg)
        assert "ambiguity_flag" in result
        assert isinstance(result["ambiguity_flag"], bool)
