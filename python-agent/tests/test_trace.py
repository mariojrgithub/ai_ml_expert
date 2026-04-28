from app.agent_runtime import run_agent_with_trace


def test_trace_contains_nodes(monkeypatch):
    from app import agent_runtime

    monkeypatch.setattr(
        agent_runtime,
        "generate_node",
        lambda state: {
            "draft_output": "select 1",
            "prompt_name": "sql",
            "prompt_version": "1.1.0",
            "model_name": "general",
            "grounded": True,
        },
    )
    monkeypatch.setattr(
        agent_runtime,
        "retrieve_node",
        lambda state: {
            "retrieved_docs": [],
            "citations": [],
            "retrieval_stats": {"doc_count": 0},
        },
    )
    monkeypatch.setattr(
        agent_runtime,
        "web_search_node",
        lambda state: {
            "external_results": [],
            "citations": [],
            "external_stats": {"result_count": 0},
        },
    )
    monkeypatch.setattr(
        agent_runtime,
        "validate_node",
        lambda state: {
            "validated_output": "select 1",
            "warnings": [],
        },
    )

    result = run_agent_with_trace("s1", "Generate a SQL query")
    assert len(result["trace"]) == 6