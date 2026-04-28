from app.router import classify_intent, plan_context


def test_classify_python_code():
    result = classify_intent("Write Python code for a JSON parser")
    assert result["intent"] == "CODE"
    assert result["domain"] == "python"


def test_plan_context_marks_freshness():
    result = plan_context("What are the latest CI/CD recommendations?", "QA")
    assert result["needs_web_search"] is True