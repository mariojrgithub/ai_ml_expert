"""Tests for Chunk 9 — rolling session summaries."""
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# store.py: load_session_summary / upsert_session_summary
# ---------------------------------------------------------------------------

def test_load_summary_returns_empty_for_new_session():
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = None
    with patch("app.store.chat_session_summaries_collection", return_value=mock_coll):
        from app.store import load_session_summary
        result = load_session_summary("sess-new")
    assert result == ""


def test_load_summary_returns_stored_text():
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = {"summary": "User discussed Python sorting."}
    with patch("app.store.chat_session_summaries_collection", return_value=mock_coll):
        from app.store import load_session_summary
        result = load_session_summary("sess-abc")
    assert result == "User discussed Python sorting."


def test_upsert_summary_calls_update_one():
    mock_coll = MagicMock()
    with patch("app.store.chat_session_summaries_collection", return_value=mock_coll):
        from app.store import upsert_session_summary
        upsert_session_summary("sess-x", "New summary text")
    mock_coll.update_one.assert_called_once()
    args = mock_coll.update_one.call_args
    assert args[0][0] == {"session_id": "sess-x"}  # filter
    assert "summary" in args[0][1]["$set"]
    assert args[1]["upsert"] is True


# ---------------------------------------------------------------------------
# memory.py: update_session_summary
# ---------------------------------------------------------------------------

def test_update_session_summary_calls_upsert():
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "Summary: user asked about Docker."

    with (
        patch("app.memory.load_session_summary", return_value=""),
        patch("app.memory.upsert_session_summary") as mock_upsert,
        patch("app.llm.general_llm", return_value=mock_llm),
    ):
        from app.memory import update_session_summary
        update_session_summary("sess-y", "What is Docker?", "Docker is a container runtime.")

    mock_upsert.assert_called_once()
    call_args = mock_upsert.call_args[0]
    assert call_args[0] == "sess-y"
    assert "Docker" in call_args[1]


def test_update_session_summary_passes_current_summary():
    """The current summary should be included in the LLM prompt."""
    mock_llm = MagicMock()
    captured = {}

    def fake_invoke(messages):
        captured["prompt"] = messages[0].content
        r = MagicMock()
        r.content = "Updated summary"
        return r

    mock_llm.invoke = fake_invoke

    with (
        patch("app.memory.load_session_summary", return_value="Prior summary text"),
        patch("app.memory.upsert_session_summary"),
        patch("app.llm.general_llm", return_value=mock_llm),
    ):
        from app.memory import update_session_summary
        update_session_summary("sess-z", "New question", "New answer")

    assert "Prior summary text" in captured["prompt"]


def test_update_session_summary_swallows_llm_exception():
    """Exceptions from the LLM must not propagate — summary is non-critical."""
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("model down")

    with (
        patch("app.memory.load_session_summary", return_value=""),
        patch("app.memory.upsert_session_summary") as mock_upsert,
        patch("app.llm.general_llm", return_value=mock_llm),
    ):
        from app.memory import update_session_summary
        # Should not raise
        update_session_summary("sess-err", "question", "answer")

    mock_upsert.assert_not_called()


def test_update_session_summary_does_not_upsert_empty_summary():
    """An empty LLM response must not be stored."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "   "

    with (
        patch("app.memory.load_session_summary", return_value=""),
        patch("app.memory.upsert_session_summary") as mock_upsert,
        patch("app.llm.general_llm", return_value=mock_llm),
    ):
        from app.memory import update_session_summary
        update_session_summary("sess-empty", "q", "a")

    mock_upsert.assert_not_called()


# ---------------------------------------------------------------------------
# get_session_summary (store read wrapper)
# ---------------------------------------------------------------------------

def test_get_session_summary_returns_stored():
    with patch("app.memory.load_session_summary", return_value="Stored summary"):
        from app.memory import get_session_summary
        assert get_session_summary("sess-s") == "Stored summary"


def test_get_session_summary_returns_empty_when_none():
    with patch("app.memory.load_session_summary", return_value=""):
        from app.memory import get_session_summary
        assert get_session_summary("sess-new") == ""
