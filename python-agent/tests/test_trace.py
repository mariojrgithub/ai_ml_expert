from app.agent_runtime import run_agent_with_trace, web_search_node


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
    nodes = [entry["node"] for entry in result["trace"]]

    # Core pipeline nodes should always be present in order, while generation
    # may appear multiple times because of relevance-driven revisions.
    expected_core = [
        "route_intent",
        "context_plan",
        "memory_read",
        "retrieve",
        "web_search",
        "validate",
        "format_output",
        "checker",
        "abstain",
        "memory_write",
        "finalize",
    ]

    positions = [nodes.index(name) for name in expected_core]
    assert positions == sorted(positions)
    assert "generate" in nodes


def test_web_search_node_falls_back_when_internal_context_missing(monkeypatch):
    from app import agent_runtime

    original = agent_runtime.settings.web_search_enabled
    agent_runtime.settings.web_search_enabled = True
    try:
        monkeypatch.setattr(
            agent_runtime,
            "run_web_search",
            lambda query: [
                {
                    "source": "web",
                    "title": "Latest CI/CD guidance",
                    "snippet": "Use trunk-based development and fast feedback loops.",
                    "url": "https://example.com/cicd",
                }
            ],
        )

        result = web_search_node(
            {
                "user_input": "What are good CI/CD practices?",
                "intent": "QA",
                "needs_web_search": False,
                "retrieved_docs": [],
                "citations": [],
            }
        )

        assert result["external_stats"]["result_count"] == 1
        assert result["external_results"][0]["title"] == "Latest CI/CD guidance"
        assert result["citations"][0]["url"] == "https://example.com/cicd"
    finally:
        agent_runtime.settings.web_search_enabled = original


def test_run_agent_with_trace_uses_web_fallback_when_rag_empty(monkeypatch):
    from app import agent_runtime

    original = agent_runtime.settings.web_search_enabled
    agent_runtime.settings.web_search_enabled = True
    try:
        monkeypatch.setattr(agent_runtime, "memory_read_node", lambda state: {
            "conversation_history": [],
            "memory_context": "",
        })
        monkeypatch.setattr(agent_runtime, "memory_write_node", lambda state: {})
        monkeypatch.setattr(agent_runtime, "retrieve_node", lambda state: {
            "retrieved_docs": [],
            "citations": [],
            "retrieval_stats": {"doc_count": 0},
        })
        monkeypatch.setattr(agent_runtime, "run_web_search", lambda query: [
            {
                "source": "web",
                "title": "Python release notes",
                "snippet": "Python 3.13 includes performance and typing improvements.",
                "url": "https://example.com/python-release",
            }
        ])
        monkeypatch.setattr(agent_runtime, "generate_node", lambda state: {
            "draft_output": state["external_results"][0]["snippet"],
            "prompt_name": "qa",
            "prompt_version": "1.1.0",
            "model_name": "general",
            "grounded": bool(state.get("external_results")),
        })
        monkeypatch.setattr(agent_runtime, "validate_node", lambda state: {
            "validated_output": state["draft_output"],
            "warnings": [],
        })

        result = run_agent_with_trace("s1", "What is new in Python?")

        assert result["external_stats"]["result_count"] == 1
        assert "Python 3.13 includes performance and typing improvements." in result["final_answer"]
        assert "Python release notes" in result["final_answer"]
        assert result["grounded"] is True
    finally:
        agent_runtime.settings.web_search_enabled = original


def test_web_search_node_runs_for_qa_even_with_internal_context(monkeypatch):
    from app import agent_runtime

    original = agent_runtime.settings.web_search_enabled
    agent_runtime.settings.web_search_enabled = True
    try:
        monkeypatch.setattr(agent_runtime, "run_web_search", lambda query: [
            {
                "source": "web",
                "title": "GPT-5 overview",
                "snippet": "GPT-5 is discussed in external sources.",
                "url": "https://example.com/gpt5",
            }
        ])

        result = web_search_node(
            {
                "user_input": "what is some information on GPT-5?",
                "intent": "QA",
                "needs_web_search": False,
                "retrieved_docs": [{"title": "Unrelated internal doc"}],
                "citations": [],
            }
        )

        assert result["web_search_attempted"] is True
        assert result["external_stats"]["result_count"] == 1
        assert result["citations"][0]["title"] == "GPT-5 overview"
    finally:
        agent_runtime.settings.web_search_enabled = original