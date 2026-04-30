from app.agent_runtime import validate_node


def test_validate_node_adds_grounding_warning_for_qa():
    result = validate_node(
        {
            "intent": "QA",
            "draft_output": "I could not find sufficient internal context.",
            "warnings": [],
            "grounded": False,
            "needs_web_search": False,
            "retrieved_docs": [],
        }
    )
    assert any("Grounded internal context" in w for w in result["warnings"])


def test_validate_node_warns_when_web_search_attempted_without_results():
    result = validate_node(
        {
            "intent": "QA",
            "draft_output": "No supported answer found.",
            "warnings": [],
            "grounded": False,
            "needs_web_search": False,
            "web_search_attempted": True,
            "external_results": [],
            "retrieved_docs": [],
        }
    )
    assert any("Web search was attempted" in w for w in result["warnings"])