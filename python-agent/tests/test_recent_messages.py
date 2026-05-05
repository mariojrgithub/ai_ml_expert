"""Tests for Chunk 4 — read_recent_chat_messages loads recent messages from
chat_messages collection and excludes the current user turn.
"""
from unittest.mock import patch

from app.memory import read_recent_chat_messages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(role: str, content: str):
    return {"role": role, "content": content}


# ---------------------------------------------------------------------------
# read_recent_chat_messages
# ---------------------------------------------------------------------------

def test_returns_empty_for_new_session():
    with patch("app.memory.load_recent_messages", return_value=[]):
        result = read_recent_chat_messages("sess-new", "any input")
    assert result == []


def test_excludes_current_user_turn_when_last_message_matches():
    """The last user message (just saved before agent runs) must be excluded."""
    msgs = [
        _msg("user", "What is Docker?"),
        _msg("assistant", "Docker is a container runtime."),
        _msg("user", "How do I install it?"),  # ← this is the current user input
    ]
    with patch("app.memory.load_recent_messages", return_value=msgs):
        result = read_recent_chat_messages("sess-x", "How do I install it?")

    assert len(result) == 2
    assert result[0]["content"] == "What is Docker?"
    assert result[1]["content"] == "Docker is a container runtime."


def test_does_not_exclude_non_matching_last_message():
    """If the last message does not match user_input, nothing is removed."""
    msgs = [
        _msg("user", "What is Docker?"),
        _msg("assistant", "Docker is a container runtime."),
    ]
    with patch("app.memory.load_recent_messages", return_value=msgs):
        result = read_recent_chat_messages("sess-y", "Different question")

    assert len(result) == 2


def test_does_not_exclude_when_last_message_is_assistant():
    """Even if the last message role is 'assistant', nothing is removed."""
    msgs = [
        _msg("user", "Ask something"),
        _msg("assistant", "Answer here"),
    ]
    with patch("app.memory.load_recent_messages", return_value=msgs):
        result = read_recent_chat_messages("sess-z", "Ask something")

    # Last message is assistant, not user — nothing stripped
    assert len(result) == 2


def test_returns_role_and_content_only():
    """Result dicts must have exactly role and content keys."""
    msgs = [
        {"role": "user", "content": "Hi", "created_at": "2024-01-01", "extra": "ignored"},
        {"role": "assistant", "content": "Hello", "metadata": {"intent": "QA"}},
    ]
    with patch("app.memory.load_recent_messages", return_value=msgs):
        result = read_recent_chat_messages("sess-keys", "different")

    for item in result:
        assert set(item.keys()) == {"role", "content"}


def test_loads_from_chat_messages_not_sessions():
    """Must call load_recent_messages (chat_messages collection), not load_session_turns."""
    called = {}

    def fake_load(session_id, limit):
        called["session_id"] = session_id
        called["limit"] = limit
        return []

    with patch("app.memory.load_recent_messages", side_effect=fake_load):
        read_recent_chat_messages("sess-abc", "q")

    assert called["session_id"] == "sess-abc"
    assert called["limit"] >= 1


def test_empty_after_stripping_only_message():
    """If there is exactly one message and it matches current input, return []."""
    msgs = [_msg("user", "single question")]
    with patch("app.memory.load_recent_messages", return_value=msgs):
        result = read_recent_chat_messages("sess-one", "single question")
    assert result == []


# ---------------------------------------------------------------------------
# memory_read_node integration: recent_messages appears in state
# ---------------------------------------------------------------------------

def test_memory_read_node_populates_recent_messages():
    """memory_read_node must set recent_messages and recent_messages_count."""
    from app.agent_runtime import memory_read_node

    fake_msgs = [
        {"role": "user", "content": "Prior question"},
        {"role": "assistant", "content": "Prior answer"},
    ]
    with (
        patch("app.memory.load_session_turns", return_value=[]),
        patch("app.memory.load_recent_messages", return_value=fake_msgs),
    ):
        state = {"session_id": "sess-node", "user_input": "Current question"}
        updates = memory_read_node(state)

    assert "recent_messages" in updates
    assert updates["recent_messages_count"] == 2
    # Both messages returned (neither matches 'Current question')
    assert len(updates["recent_messages"]) == 2


def test_memory_read_node_count_is_zero_for_fresh_session():
    with (
        patch("app.memory.load_session_turns", return_value=[]),
        patch("app.memory.load_recent_messages", return_value=[]),
    ):
        from app.agent_runtime import memory_read_node
        state = {"session_id": "sess-fresh", "user_input": "Hello"}
        updates = memory_read_node(state)

    assert updates["recent_messages"] == []
    assert updates["recent_messages_count"] == 0
