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