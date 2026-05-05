"""Chunk 10 tests — session_summary integrated into memory_read_node and
build_conversation_context."""
from unittest.mock import patch, MagicMock

import pytest
from app.memory import build_conversation_context


# ---------------------------------------------------------------------------
# build_conversation_context — summary-aware behaviour
# ---------------------------------------------------------------------------

def _m(role, content):
    return {"role": role, "content": content}


def test_build_includes_summary_preamble():
    msgs = [_m("user", "Hello"), _m("assistant", "Hi")]
    result = build_conversation_context(msgs, session_summary="Prior topic: Docker.")
    assert "Session summary" in result
    assert "Prior topic: Docker." in result
    assert "Prior conversation (recent turns):" in result


def test_build_summary_only_no_messages():
    result = build_conversation_context([], session_summary="User discussed Python basics.")
    assert "Session summary" in result
    assert "User discussed Python basics." in result
    # No empty recent turns section
    assert "Prior conversation" not in result


def test_build_empty_summary_and_messages_returns_empty():
    assert build_conversation_context([], session_summary="") == ""


def test_build_empty_summary_with_messages_no_summary_label():
    msgs = [_m("user", "q"), _m("assistant", "a")]
    result = build_conversation_context(msgs, session_summary="")
    assert "Session summary" not in result
    assert "Prior conversation (recent turns):" in result


def test_build_summary_stripped_of_whitespace():
    result = build_conversation_context([], session_summary="  padded  ")
    assert "padded" in result
    # Should not start/end with whitespace in the preamble
    assert "  padded  " not in result


# ---------------------------------------------------------------------------
# memory_read_node — populates session_summary in state
# ---------------------------------------------------------------------------

def test_memory_read_node_populates_session_summary():
    """memory_read_node must include session_summary in the returned state."""
    from app.agent_runtime import memory_read_node

    state = {"session_id": "s-abc", "user_input": "What is Python?"}
    with (
        patch("app.agent_runtime.read_session_memory", return_value=([], "")),
        patch("app.agent_runtime.read_recent_chat_messages", return_value=[]),
        patch("app.agent_runtime.get_session_summary", return_value="Summary text") as mock_summary,
    ):
        updates = memory_read_node(state)

    mock_summary.assert_called_once_with("s-abc")
    assert updates["session_summary"] == "Summary text"


def test_memory_read_node_empty_summary_when_none():
    from app.agent_runtime import memory_read_node

    state = {"session_id": "s-new", "user_input": "Hello"}
    with (
        patch("app.agent_runtime.read_session_memory", return_value=([], "")),
        patch("app.agent_runtime.read_recent_chat_messages", return_value=[]),
        patch("app.agent_runtime.get_session_summary", return_value=""),
    ):
        updates = memory_read_node(state)

    assert updates["session_summary"] == ""
