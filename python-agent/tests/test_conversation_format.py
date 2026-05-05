"""Tests for Chunk 5 — conversation formatting utilities in memory.py."""
from app.memory import format_recent_messages_as_text, build_conversation_context


def _m(role, content):
    return {"role": role, "content": content}


# ---------------------------------------------------------------------------
# format_recent_messages_as_text
# ---------------------------------------------------------------------------

def test_empty_list_returns_empty_string():
    assert format_recent_messages_as_text([]) == ""


def test_single_user_message():
    result = format_recent_messages_as_text([_m("user", "Hello")])
    assert result == "User: Hello"


def test_user_and_assistant():
    msgs = [_m("user", "What is Python?"), _m("assistant", "A programming language.")]
    result = format_recent_messages_as_text(msgs)
    assert result == "User: What is Python?\nAssistant: A programming language."


def test_role_is_capitalized():
    result = format_recent_messages_as_text([_m("user", "hi")])
    assert result.startswith("User:")


def test_long_message_is_truncated():
    long_content = "x" * 600
    result = format_recent_messages_as_text(
        [_m("user", long_content)], max_chars_per_message=500
    )
    assert len(result) < 600
    assert "[...]" in result


def test_short_message_not_truncated():
    content = "Short message"
    result = format_recent_messages_as_text([_m("user", content)])
    assert "[...]" not in result
    assert content in result


def test_total_char_budget_drops_oldest_messages():
    # 5 messages, each ~60 chars; set budget to 120 so only ~2 survive
    msgs = [_m("user", f"Question number {i}" + " " * 40) for i in range(5)]
    result = format_recent_messages_as_text(msgs, max_total_chars=120)
    lines = result.strip().splitlines()
    # Should have fewer than 5 lines
    assert len(lines) < 5


def test_total_char_budget_keeps_most_recent():
    msgs = [
        _m("user", "Old question here"),
        _m("assistant", "Old answer here"),
        _m("user", "Recent question here"),
        _m("assistant", "Recent answer here"),
    ]
    # Budget forces drop of old messages
    result = format_recent_messages_as_text(msgs, max_total_chars=60)
    assert "Recent" in result


def test_empty_content_is_allowed():
    msgs = [_m("user", ""), _m("assistant", "")]
    result = format_recent_messages_as_text(msgs)
    assert "User:" in result
    assert "Assistant:" in result


# ---------------------------------------------------------------------------
# build_conversation_context
# ---------------------------------------------------------------------------

def test_build_returns_empty_string_for_empty_messages():
    assert build_conversation_context([]) == ""


def test_build_includes_label():
    msgs = [_m("user", "Hello"), _m("assistant", "Hi")]
    result = build_conversation_context(msgs)
    assert result.startswith("Prior conversation (recent turns):")


def test_build_includes_message_content():
    msgs = [_m("user", "What is a list?"), _m("assistant", "A collection type.")]
    result = build_conversation_context(msgs)
    assert "What is a list?" in result
    assert "A collection type." in result
