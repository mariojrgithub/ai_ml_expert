"""Tests for app.memory — read/write without a real MongoDB connection.

pymongo and pydantic_settings are Docker-only; they are stubbed by conftest.py.
"""
import sys
from unittest.mock import MagicMock, patch

# Now safe to import app.memory (and its transitive deps)
from app.memory import read_session_memory, write_session_memory  # noqa: E402


# ---------------------------------------------------------------------------
# read_session_memory
# ---------------------------------------------------------------------------

def test_read_session_memory_returns_empty_when_no_turns():
    with patch("app.memory.load_session_turns", return_value=[]):
        turns, ctx = read_session_memory("sess-123")
    assert turns == []
    assert ctx == ""


def test_read_session_memory_renders_prior_turns():
    fake_turns = [
        {"user_input": "What is Docker?", "final_answer": "Docker is a container runtime."},
        {"user_input": "How do I install it?", "final_answer": "Run apt install docker."},
    ]
    with patch("app.memory.load_session_turns", return_value=fake_turns):
        turns, ctx = read_session_memory("sess-abc")

    assert len(turns) == 2
    assert "Docker" in ctx
    assert "Prior session context" in ctx


def test_read_session_memory_caps_at_max_turns():
    many_turns = [
        {"user_input": f"q{i}", "final_answer": f"a{i}"}
        for i in range(10)
    ]
    with patch("app.memory.load_session_turns", return_value=many_turns):
        turns, ctx = read_session_memory("sess-xyz")

    # Only last _MAX_TURNS_IN_PROMPT (4) turns should appear
    assert ctx.count("User:") <= 4


# ---------------------------------------------------------------------------
# write_session_memory
# ---------------------------------------------------------------------------

def test_write_session_memory_does_not_write_when_abstain():
    with patch("app.memory.save_session_turn") as mock_save:
        write_session_memory(
            session_id="s1", user_input="q", final_answer="a",
            intent="QA", grounded=True, abstain=True,
        )
        mock_save.assert_not_called()


def test_write_session_memory_does_not_write_when_ungrounded():
    with patch("app.memory.save_session_turn") as mock_save:
        write_session_memory(
            session_id="s1", user_input="q", final_answer="a",
            intent="QA", grounded=False, abstain=False,
        )
        mock_save.assert_not_called()


def test_write_session_memory_writes_when_grounded_and_not_abstaining():
    with patch("app.memory.save_session_turn") as mock_save:
        write_session_memory(
            session_id="s1", user_input="What is CI/CD?",
            final_answer="CI/CD means continuous integration.",
            intent="QA", grounded=True, abstain=False,
        )
        mock_save.assert_called_once()
        _, call_kwargs = mock_save.call_args
        assert call_kwargs["session_id"] == "s1"
