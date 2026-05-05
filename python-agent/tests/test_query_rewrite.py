"""Tests for Chunk 6 — query_rewrite_node uses recent_messages (all turns)
in preference to legacy memory_context (grounded-only sessions).
"""
from unittest.mock import MagicMock, patch

from app.agent_runtime import query_rewrite_node


def _state(**kwargs):
    base = {
        "session_id": "sess-qr",
        "user_input": "How do I install it?",
        "recent_messages": [],
        "memory_context": "",
        "conversation_history": [],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# No history → pass-through
# ---------------------------------------------------------------------------

def test_no_history_returns_original_input():
    state = _state(recent_messages=[], memory_context="")
    result = query_rewrite_node(state)
    assert result["retrieval_query"] == "How do I install it?"


def test_empty_recent_and_context_no_llm_call():
    """LLM must NOT be called when there is no history."""
    state = _state(recent_messages=[], memory_context="")
    with patch("app.agent_runtime.general_llm") as mock_llm:
        query_rewrite_node(state)
    mock_llm.assert_not_called()


# ---------------------------------------------------------------------------
# recent_messages takes priority
# ---------------------------------------------------------------------------

def test_recent_messages_used_when_present():
    recent = [
        {"role": "user", "content": "What is Docker?"},
        {"role": "assistant", "content": "Docker is a container runtime."},
    ]
    mock_llm = MagicMock()
    mock_llm.return_value.invoke.return_value.content = "How to install Docker"
    with patch("app.agent_runtime.general_llm", return_value=mock_llm.return_value):
        state = _state(recent_messages=recent, memory_context="")
        result = query_rewrite_node(state)
    assert result["retrieval_query"] == "How to install Docker"


def test_recent_messages_preferred_over_memory_context():
    """When both recent_messages and memory_context are set, use recent_messages."""
    recent = [
        {"role": "user", "content": "Explain recursion"},
        {"role": "assistant", "content": "Recursion is..."},
    ]
    mock_llm = MagicMock()
    captured = {}

    def fake_invoke(messages):
        captured["prompt"] = messages[0].content
        result = MagicMock()
        result.content = "recursion in Python"
        return result

    mock_llm.invoke = fake_invoke
    with patch("app.agent_runtime.general_llm", return_value=mock_llm):
        state = _state(
            recent_messages=recent,
            memory_context="Prior session context (unverified):\nUser: old thing",
        )
        query_rewrite_node(state)

    # Prompt should contain recent message content, NOT memory_context prefix
    assert "Explain recursion" in captured["prompt"]


# ---------------------------------------------------------------------------
# Fallback to memory_context when recent_messages is empty
# ---------------------------------------------------------------------------

def test_falls_back_to_memory_context_when_no_recent_messages():
    """If recent_messages is empty but memory_context exists, still rewrites."""
    mock_llm = MagicMock()
    mock_llm.return_value.invoke.return_value.content = "standalone query"
    with patch("app.agent_runtime.general_llm", return_value=mock_llm.return_value):
        state = _state(
            recent_messages=[],
            memory_context="Prior session context (unverified):\nUser: prior q\nAssistant: prior a",
        )
        result = query_rewrite_node(state)
    assert result["retrieval_query"] == "standalone query"


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

def test_llm_exception_falls_back_to_original_input():
    recent = [{"role": "user", "content": "prior"}, {"role": "assistant", "content": "ans"}]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("model unavailable")
    with patch("app.agent_runtime.general_llm", return_value=mock_llm):
        state = _state(recent_messages=recent)
        result = query_rewrite_node(state)
    assert result["retrieval_query"] == "How do I install it?"


def test_empty_llm_response_falls_back_to_original_input():
    recent = [{"role": "user", "content": "prior"}, {"role": "assistant", "content": "ans"}]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = ""
    with patch("app.agent_runtime.general_llm", return_value=mock_llm):
        state = _state(recent_messages=recent)
        result = query_rewrite_node(state)
    assert result["retrieval_query"] == "How do I install it?"


def test_overly_long_llm_response_falls_back_to_original_input():
    recent = [{"role": "user", "content": "prior"}, {"role": "assistant", "content": "ans"}]
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "x" * 501  # exceeds 500 char limit
    with patch("app.agent_runtime.general_llm", return_value=mock_llm):
        state = _state(recent_messages=recent)
        result = query_rewrite_node(state)
    assert result["retrieval_query"] == "How do I install it?"
